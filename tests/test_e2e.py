"""
test_e2e.py — End-to-end integration tests for the anonymizer hook pipeline.

Tests the full flow as Claude Code would invoke it:
  PreToolUse  → hook_router (stdin JSON) → anonymize / deny / approve
  PostToolUse → restore (stdin JSON)     → token reversal in files
  Round-trip  → Read(脫敏) → Write(帶 token) → restore(還原)
"""

import json
import os
import shutil
import tempfile

import pytest

from hook_router import handle_pretool_use
from restore import handle_post_tool_use
from mapping_manager import TOKEN_PATTERN, TMP_ANONYMIZER_DIR


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def e2e_env(tmp_path):
    """Create an isolated scan directory and temp mapping directory for each test."""
    scan_dir = tmp_path / "scan"
    scan_dir.mkdir()
    mappings_dir = tmp_path / "mappings"
    mappings_dir.mkdir()

    config = {
        "auto_detect": True,
        "custom_terms": {
            "schools": ["國立台灣大學"],
            "people": ["王小明"],
        },
        "substring_match": True,
        "scan_paths": [str(scan_dir) + "/"],
        "file_types": [".txt", ".md"],
        "persist_mapping": True,
    }

    return {
        "scan_dir": scan_dir,
        "mappings_dir": mappings_dir,
        "config": config,
    }


# ---------------------------------------------------------------------------
# 1. PreToolUse Read — full anonymization round-trip
# ---------------------------------------------------------------------------

class TestE2EPreToolUseRead:
    """Read hook: file with PII → intercepted → temp file with tokens returned."""

    def test_read_sensitive_file_returns_anonymized_temp(self, e2e_env):
        """A file containing custom terms is redirected to a temp file with tokens."""
        scan_dir = e2e_env["scan_dir"]
        config = e2e_env["config"]

        # Create a sensitive file
        sensitive = scan_dir / "report.txt"
        sensitive.write_text("國立台灣大學資訊工程系王小明的成績報告", encoding="utf-8")

        stdin_data = {
            "session_id": "e2e_test_read",
            "tool_name": "Read",
            "tool_input": {"file_path": str(sensitive)},
        }

        result = handle_pretool_use(stdin_data, config, use_ner=False)

        # Should return updatedInput with a different file_path
        assert "hookSpecificOutput" in result
        hook_out = result["hookSpecificOutput"]
        assert hook_out["hookEventName"] == "PreToolUse"
        assert "updatedInput" in hook_out

        anon_path = hook_out["updatedInput"]["file_path"]
        assert anon_path != str(sensitive)
        assert os.path.isfile(anon_path)

        # The anonymized content should contain tokens, not the original terms
        anon_content = open(anon_path, encoding="utf-8").read()
        assert "國立台灣大學" not in anon_content
        assert "王小明" not in anon_content
        assert TOKEN_PATTERN.search(anon_content) is not None

        # additionalContext should mention anonymization
        assert "脫敏" in hook_out.get("additionalContext", "")

    def test_read_clean_file_approves_original(self, e2e_env):
        """A file with no PII passes through unchanged."""
        scan_dir = e2e_env["scan_dir"]
        config = e2e_env["config"]

        clean = scan_dir / "clean.txt"
        clean.write_text("今天天氣很好，適合出門散步。", encoding="utf-8")

        stdin_data = {
            "session_id": "e2e_test_clean",
            "tool_name": "Read",
            "tool_input": {"file_path": str(clean)},
        }

        result = handle_pretool_use(stdin_data, config, use_ner=False)
        assert result == {}  # approve, no redirection

    def test_read_non_scan_path_approves(self, e2e_env):
        """A file outside scan_paths is approved without inspection."""
        config = e2e_env["config"]

        stdin_data = {
            "session_id": "e2e_outside",
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/random_file.txt"},
        }

        result = handle_pretool_use(stdin_data, config, use_ner=False)
        assert result == {}

    def test_read_wrong_file_type_approves(self, e2e_env):
        """A file with a non-matching extension in scan_paths is approved."""
        scan_dir = e2e_env["scan_dir"]
        config = e2e_env["config"]

        py_file = scan_dir / "script.py"
        py_file.write_text("# 國立台灣大學", encoding="utf-8")

        stdin_data = {
            "session_id": "e2e_ext",
            "tool_name": "Read",
            "tool_input": {"file_path": str(py_file)},
        }

        result = handle_pretool_use(stdin_data, config, use_ner=False)
        assert result == {}  # .py not in file_types


# ---------------------------------------------------------------------------
# 2. PreToolUse deny paths (Edit / Grep / Bash)
# ---------------------------------------------------------------------------

class TestE2EPreToolUseDeny:
    """Edit, Grep, Bash on scan_paths are denied."""

    def test_edit_scan_path_denied(self, e2e_env):
        config = e2e_env["config"]
        scan_dir = e2e_env["scan_dir"]

        stdin_data = {
            "session_id": "e2e_deny_edit",
            "tool_name": "Edit",
            "tool_input": {"file_path": str(scan_dir / "report.txt")},
        }

        result = handle_pretool_use(stdin_data, config, use_ner=False)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_grep_scan_path_denied(self, e2e_env):
        config = e2e_env["config"]
        scan_dir = e2e_env["scan_dir"]

        stdin_data = {
            "session_id": "e2e_deny_grep",
            "tool_name": "Grep",
            "tool_input": {"path": str(scan_dir), "pattern": "大學"},
        }

        result = handle_pretool_use(stdin_data, config, use_ner=False)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_bash_cat_scan_path_denied(self, e2e_env):
        config = e2e_env["config"]
        scan_dir = e2e_env["scan_dir"]

        stdin_data = {
            "session_id": "e2e_deny_bash",
            "tool_name": "Bash",
            "tool_input": {"command": f"cat {scan_dir}/report.txt"},
        }

        result = handle_pretool_use(stdin_data, config, use_ner=False)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_bash_safe_command_approved(self, e2e_env):
        config = e2e_env["config"]

        stdin_data = {
            "session_id": "e2e_safe_bash",
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
        }

        result = handle_pretool_use(stdin_data, config, use_ner=False)
        assert result == {}

    def test_edit_anonymized_temp_approved(self, e2e_env):
        """Editing an already-anonymized temp file is allowed."""
        config = e2e_env["config"]

        stdin_data = {
            "session_id": "e2e_edit_temp",
            "tool_name": "Edit",
            "tool_input": {"file_path": os.path.join(TMP_ANONYMIZER_DIR, "anonymized_abc123.txt")},
        }

        result = handle_pretool_use(stdin_data, config, use_ner=False)
        assert result == {}


# ---------------------------------------------------------------------------
# 3. PostToolUse restore — token reversal
# ---------------------------------------------------------------------------

class TestE2EPostToolUseRestore:
    """PostToolUse restore hook reverses tokens back to original values."""

    def test_restore_replaces_tokens_in_written_file(self, e2e_env):
        """A file containing __ANON:*__ tokens is restored to original values."""
        mappings_dir = e2e_env["mappings_dir"]

        # Pre-populate a session mapping file (simulating what PreToolUse created)
        from mapping_manager import MappingManager
        session_id = "e2e_restore"
        mgr = MappingManager(session_id=session_id, mappings_dir=str(mappings_dir))
        token_school = mgr.get_or_create_token("國立台灣大學", "SCHOOL")
        token_person = mgr.get_or_create_token("王小明", "PERSON")
        mgr.save()

        # Create a file that Claude "wrote" with tokens
        output_file = e2e_env["scan_dir"] / "output.txt"
        output_file.write_text(
            f"{token_school}資訊工程系{token_person}的成績報告",
            encoding="utf-8",
        )

        stdin_data = {
            "session_id": session_id,
            "tool_name": "Write",
            "tool_input": {"file_path": str(output_file)},
        }

        handle_post_tool_use(stdin_data, mappings_dir=str(mappings_dir))

        restored = output_file.read_text(encoding="utf-8")
        assert "國立台灣大學" in restored
        assert "王小明" in restored
        assert TOKEN_PATTERN.search(restored) is None

    def test_restore_no_tokens_leaves_file_unchanged(self, e2e_env):
        """A file without tokens is not modified."""
        mappings_dir = e2e_env["mappings_dir"]
        output_file = e2e_env["scan_dir"] / "normal.txt"
        original = "普通的文件內容，沒有任何 token。"
        output_file.write_text(original, encoding="utf-8")

        stdin_data = {
            "session_id": "e2e_no_token",
            "tool_name": "Write",
            "tool_input": {"file_path": str(output_file)},
        }

        handle_post_tool_use(stdin_data, mappings_dir=str(mappings_dir))

        assert output_file.read_text(encoding="utf-8") == original

    def test_restore_ignores_non_write_tools(self, e2e_env):
        """PostToolUse on Read tool does nothing."""
        mappings_dir = e2e_env["mappings_dir"]
        output_file = e2e_env["scan_dir"] / "ignored.txt"
        output_file.write_text("__ANON:SCHOOL_001__", encoding="utf-8")

        stdin_data = {
            "session_id": "e2e_ignore",
            "tool_name": "Read",
            "tool_input": {"file_path": str(output_file)},
        }

        handle_post_tool_use(stdin_data, mappings_dir=str(mappings_dir))

        # File should remain untouched — Read is not a write tool
        assert output_file.read_text(encoding="utf-8") == "__ANON:SCHOOL_001__"


# ---------------------------------------------------------------------------
# 4. Full round-trip: Read(脫敏) → Write(帶token) → restore(還原)
# ---------------------------------------------------------------------------

class TestE2EFullRoundTrip:
    """Simulate the complete Claude Code interaction cycle."""

    def test_full_round_trip_preserves_content(self, e2e_env):
        """
        1. A file with PII is Read → hook redirects to anonymized temp
        2. Claude reads the temp file (tokens visible)
        3. Claude writes a new file containing some tokens
        4. PostToolUse restore hook reverses tokens
        5. Final file contains original PII values
        """
        scan_dir = e2e_env["scan_dir"]
        config = e2e_env["config"]

        # --- Step 1: Create sensitive source file ---
        original_text = "國立台灣大學資訊工程系王小明教授的研究計畫"
        source = scan_dir / "research.txt"
        source.write_text(original_text, encoding="utf-8")

        # --- Step 2: PreToolUse Read → anonymization ---
        read_stdin = {
            "session_id": "e2e_roundtrip",
            "tool_name": "Read",
            "tool_input": {"file_path": str(source)},
        }

        read_result = handle_pretool_use(read_stdin, config, use_ner=False)

        assert "hookSpecificOutput" in read_result
        anon_path = read_result["hookSpecificOutput"]["updatedInput"]["file_path"]
        anon_content = open(anon_path, encoding="utf-8").read()

        # Verify tokens are present
        assert "國立台灣大學" not in anon_content
        assert "王小明" not in anon_content
        tokens_found = TOKEN_PATTERN.findall(anon_content)
        assert len(tokens_found) >= 2  # at least school + person

        # --- Step 3: Claude "processes" and writes a new file with tokens ---
        # Simulate Claude adding a summary line while keeping tokens
        claude_output = f"摘要：{anon_content}\n以上為研究計畫摘要。"
        output_file = scan_dir / "summary.txt"
        output_file.write_text(claude_output, encoding="utf-8")

        # --- Step 4: PostToolUse restore ---
        # The session mapping was saved under the Claude session id from Step 2.
        write_stdin = {
            "session_id": read_stdin["session_id"],
            "tool_name": "Write",
            "tool_input": {"file_path": str(output_file)},
        }

        handle_post_tool_use(write_stdin)  # uses default /tmp/anonymizer mappings_dir

        # --- Step 5: Verify restoration ---
        final_content = output_file.read_text(encoding="utf-8")
        assert "國立台灣大學" in final_content
        assert "王小明" in final_content
        assert TOKEN_PATTERN.search(final_content) is None
        assert "以上為研究計畫摘要" in final_content

    def test_round_trip_edit_tool_also_restores(self, e2e_env):
        """
        PostToolUse for Edit tool also triggers restoration.
        """
        scan_dir = e2e_env["scan_dir"]
        config = e2e_env["config"]

        # Create and anonymize
        source = scan_dir / "notes.md"
        source.write_text("王小明在國立台灣大學的筆記", encoding="utf-8")

        read_stdin = {
            "session_id": "e2e_edit_roundtrip",
            "tool_name": "Read",
            "tool_input": {"file_path": str(source)},
        }

        read_result = handle_pretool_use(read_stdin, config, use_ner=False)
        anon_path = read_result["hookSpecificOutput"]["updatedInput"]["file_path"]
        anon_content = open(anon_path, encoding="utf-8").read()

        # Simulate Claude editing and creating a file with tokens
        edited_file = scan_dir / "edited_notes.md"
        edited_file.write_text(f"已編輯：{anon_content}", encoding="utf-8")

        # PostToolUse Edit
        edit_stdin = {
            "session_id": read_stdin["session_id"],
            "tool_name": "Edit",
            "tool_input": {"file_path": str(edited_file)},
        }

        handle_post_tool_use(edit_stdin)

        final = edited_file.read_text(encoding="utf-8")
        assert "王小明" in final
        assert "國立台灣大學" in final
        assert TOKEN_PATTERN.search(final) is None
