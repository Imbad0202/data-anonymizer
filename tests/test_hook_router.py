import pytest
import os
import tempfile
from hook_router import handle_pretool_use
from mapping_manager import TMP_ANONYMIZER_DIR

class TestHookRouter:
    def setup_method(self):
        self.config = {
            "auto_detect": True,
            "custom_terms": {"schools": ["國立OO大學"]},
            "substring_match": True,
            "scan_paths": ["/tmp/test_scan/"],
            "file_types": [".md", ".txt"],
        }
        os.makedirs("/tmp/test_scan", exist_ok=True)

    def test_read_sensitive_file_returns_updated_input(self):
        test_file = "/tmp/test_scan/test.md"
        with open(test_file, 'w') as f:
            f.write("國立OO大學的報告")
        stdin_data = {"session_id": "test_session", "tool_name": "Read", "tool_input": {"file_path": test_file}}
        result = handle_pretool_use(stdin_data, self.config, use_ner=False)
        assert "hookSpecificOutput" in result
        assert "updatedInput" in result["hookSpecificOutput"]
        assert result["hookSpecificOutput"]["updatedInput"]["file_path"] != test_file
        assert result["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
        os.unlink(test_file)

    def test_read_non_sensitive_path_approves(self):
        stdin_data = {"session_id": "test_session", "tool_name": "Read", "tool_input": {"file_path": "/Users/imbad/other.md"}}
        result = handle_pretool_use(stdin_data, self.config, use_ner=False)
        assert result == {}

    def test_read_anonymizer_internal_denied(self):
        stdin_data = {"session_id": "test_session", "tool_name": "Read", "tool_input": {"file_path": os.path.expanduser("~/.claude/anonymizer/config.json")}}
        result = handle_pretool_use(stdin_data, self.config, use_ner=False)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_edit_sensitive_file_denied(self):
        stdin_data = {"session_id": "test_session", "tool_name": "Edit", "tool_input": {"file_path": "/tmp/test_scan/test.md"}}
        result = handle_pretool_use(stdin_data, self.config, use_ner=False)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_edit_anonymized_temp_approved(self):
        stdin_data = {"session_id": "test_session", "tool_name": "Edit", "tool_input": {"file_path": os.path.join(TMP_ANONYMIZER_DIR, "anonymized_abc123.txt")}}
        result = handle_pretool_use(stdin_data, self.config, use_ner=False)
        assert result == {}

    def test_grep_sensitive_path_denied(self):
        stdin_data = {"session_id": "test_session", "tool_name": "Grep", "tool_input": {"path": "/tmp/test_scan/", "pattern": "test"}}
        result = handle_pretool_use(stdin_data, self.config, use_ner=False)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_bash_with_sensitive_path_denied(self):
        stdin_data = {"session_id": "test_session", "tool_name": "Bash", "tool_input": {"command": "cat /tmp/test_scan/test.md"}}
        result = handle_pretool_use(stdin_data, self.config, use_ner=False)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_bash_safe_command_approved(self):
        stdin_data = {"session_id": "test_session", "tool_name": "Bash", "tool_input": {"command": "ls -la /tmp/"}}
        result = handle_pretool_use(stdin_data, self.config, use_ner=False)
        assert result == {}

    def test_bash_python_reader_denied(self):
        cmd = 'python3 -c "print(open(\'/tmp/test_scan/test.md\').read())"'
        stdin_data = {"session_id": "test_session", "tool_name": "Bash", "tool_input": {"command": cmd}}
        result = handle_pretool_use(stdin_data, self.config, use_ner=False)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_read_anonymizer_source_code_allowed(self):
        """Source .py files should NOT be blocked — only config/mapping files."""
        stdin_data = {"session_id": "test_session", "tool_name": "Read", "tool_input": {"file_path": os.path.expanduser("~/.claude/anonymizer/hook_router.py")}}
        result = handle_pretool_use(stdin_data, self.config, use_ner=False)
        assert result == {}

    def test_read_anonymizer_mapping_denied(self):
        stdin_data = {"session_id": "test_session", "tool_name": "Read", "tool_input": {"file_path": os.path.expanduser("~/.claude/anonymizer/mappings/session_abc.json")}}
        result = handle_pretool_use(stdin_data, self.config, use_ner=False)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_bash_running_hook_itself_allowed(self):
        """The hook's own Python invocation must not block itself."""
        cmd = os.path.expanduser("~/.claude/anonymizer/.venv/bin/python3") + " " + os.path.expanduser("~/.claude/anonymizer/hook_router.py")
        stdin_data = {"session_id": "test_session", "tool_name": "Bash", "tool_input": {"command": cmd}}
        result = handle_pretool_use(stdin_data, self.config, use_ner=False)
        assert result == {}

    def test_bash_cat_config_denied(self):
        cmd = "cat " + os.path.expanduser("~/.claude/anonymizer/config.json")
        stdin_data = {"session_id": "test_session", "tool_name": "Bash", "tool_input": {"command": cmd}}
        result = handle_pretool_use(stdin_data, self.config, use_ner=False)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_bash_git_in_anonymizer_allowed(self):
        cmd = "cd " + os.path.expanduser("~/.claude/anonymizer") + " && git status"
        stdin_data = {"session_id": "test_session", "tool_name": "Bash", "tool_input": {"command": cmd}}
        result = handle_pretool_use(stdin_data, self.config, use_ner=False)
        assert result == {}

    def test_no_pii_approves_original(self):
        test_file = "/tmp/test_scan/clean.md"
        with open(test_file, 'w') as f:
            f.write("今天天氣很好")
        stdin_data = {"session_id": "test_session", "tool_name": "Read", "tool_input": {"file_path": test_file}}
        result = handle_pretool_use(stdin_data, self.config, use_ner=False)
        assert result == {}
        os.unlink(test_file)
