"""
hook_router.py — Entry point for ALL PreToolUse hooks (Read, Edit, Grep, Bash).

Reads stdin JSON, routes by tool_name, and outputs appropriate hook responses.
"""

import json
import os
import re
import sys
from typing import Any, Dict

# ---------------------------------------------------------------------------
# Internal path constants
# ---------------------------------------------------------------------------

ANONYMIZER_DIR = os.path.expanduser("~/.claude/anonymizer")
TMP_ANONYMIZER_DIR = "/tmp/anonymizer"

# Commands that read file contents and could leak sensitive data
FILE_READ_COMMANDS = re.compile(
    r'\b(cat|head|tail|less|more|grep|rg|awk|sed|cut|sort|uniq|strings|xxd|od|bat|view)\b'
)


# ---------------------------------------------------------------------------
# Helper: deny / approve response builders
# ---------------------------------------------------------------------------

def _deny(reason: str) -> Dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def _approve() -> Dict[str, Any]:
    return {}


def _updated_input(new_file_path: str, context: str) -> Dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "updatedInput": {"file_path": new_file_path},
            "additionalContext": context,
        }
    }


# ---------------------------------------------------------------------------
# Internal path checks
# ---------------------------------------------------------------------------

def _is_internal_file(path: str) -> bool:
    """Return True if the path is an anonymizer-internal file that should never be exposed."""
    norm = os.path.normpath(os.path.realpath(path)) if os.path.exists(path) else os.path.normpath(path)
    # ~/.claude/anonymizer/* is internal
    internal_dir = os.path.normpath(ANONYMIZER_DIR)
    if norm.startswith(internal_dir):
        return True
    # /tmp/anonymizer/session_*.json is internal
    if norm.startswith(os.path.normpath(TMP_ANONYMIZER_DIR)):
        basename = os.path.basename(norm)
        if basename.startswith("session_") and basename.endswith(".json"):
            return True
    return False


def _is_in_scan_paths(path: str, scan_paths) -> bool:
    """Return True if path falls under any configured scan_path."""
    norm_path = os.path.normpath(path)
    for sp in scan_paths:
        norm_sp = os.path.normpath(sp)
        if norm_path == norm_sp or norm_path.startswith(norm_sp + os.sep):
            return True
    return False


def _has_matching_file_type(path: str, file_types) -> bool:
    """Return True if the file extension is in the configured file_types list."""
    if not file_types:
        return True
    ext = os.path.splitext(path)[1].lower()
    return ext in [ft.lower() for ft in file_types]


def _is_anonymized_temp(path: str) -> bool:
    """Return True if the path is an /tmp/anonymizer/anonymized_* file."""
    norm = os.path.normpath(path)
    return norm.startswith(os.path.normpath(TMP_ANONYMIZER_DIR) + os.sep) and \
           os.path.basename(norm).startswith("anonymized_")


# ---------------------------------------------------------------------------
# Per-tool handlers
# ---------------------------------------------------------------------------

def _handle_read(tool_input: Dict, config: Dict, use_ner: bool) -> Dict[str, Any]:
    file_path = tool_input.get("file_path", "")
    scan_paths = config.get("scan_paths", [])
    file_types = config.get("file_types", [])

    # 1. Block internal files
    if _is_internal_file(file_path):
        return _deny("此路徑屬於脫敏器內部資料，禁止存取。")

    # 2. If file is in scan_paths AND matching file_type → try to anonymize
    if _is_in_scan_paths(file_path, scan_paths) and _has_matching_file_type(file_path, file_types):
        if not os.path.isfile(file_path):
            # File doesn't exist yet; just approve
            return _approve()

        session_id = "hook_router_session"
        from anonymizer import Anonymizer
        anon = Anonymizer(config=config, session_id=session_id, use_ner=use_ner)
        anon_path, summary = anon.anonymize_file(file_path)

        if anon_path is None:
            # No PII found
            return _approve()

        context = f"注意：此檔案已自動脫敏處理。{summary}"
        return _updated_input(anon_path, context)

    # 3. Otherwise approve
    return _approve()


def _handle_edit(tool_input: Dict, config: Dict) -> Dict[str, Any]:
    file_path = tool_input.get("file_path", "")
    scan_paths = config.get("scan_paths", [])

    # 1. Block internal files
    if _is_internal_file(file_path):
        return _deny("此路徑屬於脫敏器內部資料，禁止存取。")

    # 2. If file is in scan_paths → deny
    if _is_in_scan_paths(file_path, scan_paths):
        return _deny("此檔案包含敏感資料，不允許直接編輯")

    # 3. If editing anonymized temp file → approve
    if _is_anonymized_temp(file_path):
        return _approve()

    # 4. Otherwise → approve
    return _approve()


def _handle_grep(tool_input: Dict, config: Dict) -> Dict[str, Any]:
    path = tool_input.get("path", "")
    scan_paths = config.get("scan_paths", [])

    # 1. Block internal paths
    if _is_internal_file(path):
        return _deny("此路徑屬於脫敏器內部資料，禁止存取。")

    # 2. If path overlaps scan_paths → deny
    if _is_in_scan_paths(path, scan_paths):
        return _deny("此目錄包含敏感資料，不允許搜尋。")

    # Also deny if a scan_path is a subdirectory of the given path
    # (i.e., searching a parent that would expose scan paths)
    norm_path = os.path.normpath(path)
    for sp in scan_paths:
        norm_sp = os.path.normpath(sp)
        if norm_sp.startswith(norm_path + os.sep) or norm_sp == norm_path:
            return _deny("此目錄包含敏感資料，不允許搜尋。")

    return _approve()


def _handle_bash(tool_input: Dict, config: Dict) -> Dict[str, Any]:
    command = tool_input.get("command", "")
    scan_paths = config.get("scan_paths", [])

    # 1. Block commands targeting ~/.claude/anonymizer/
    anonymizer_dir = os.path.expanduser("~/.claude/anonymizer/")
    if anonymizer_dir in command or ANONYMIZER_DIR in command:
        return _deny("此指令嘗試存取脫敏器內部目錄，已被攔截。")

    # 2. If command contains file-read commands AND sensitive paths → deny
    if FILE_READ_COMMANDS.search(command):
        for sp in scan_paths:
            # Normalize scan path for comparison (strip trailing slash for matching)
            sp_stripped = sp.rstrip("/")
            sp_with_slash = sp if sp.endswith("/") else sp + "/"
            if sp_stripped in command or sp_with_slash in command:
                return _deny("此指令嘗試讀取受保護的資料夾，已被攔截。")

    return _approve()


# ---------------------------------------------------------------------------
# Main router
# ---------------------------------------------------------------------------

def handle_pretool_use(
    stdin_data: Dict[str, Any],
    config: Dict[str, Any],
    use_ner: bool = True,
) -> Dict[str, Any]:
    """
    Route a PreToolUse hook request and return the appropriate response dict.

    Parameters
    ----------
    stdin_data : dict
        Parsed JSON from Claude Code's hook stdin.
    config : dict
        Anonymizer configuration (scan_paths, file_types, custom_terms, etc.).
    use_ner : bool
        Whether to use NER detection (expensive; set False in tests).

    Returns
    -------
    dict
        Empty dict {} for approve, or structured hook response dict.
    """
    tool_name = stdin_data.get("tool_name", "")
    tool_input = stdin_data.get("tool_input", {})

    if tool_name == "Read":
        return _handle_read(tool_input, config, use_ner)
    elif tool_name == "Edit":
        return _handle_edit(tool_input, config)
    elif tool_name == "Grep":
        return _handle_grep(tool_input, config)
    elif tool_name == "Bash":
        return _handle_bash(tool_input, config)
    else:
        # Unknown tool → approve
        return _approve()


def main():
    """CLI entry point: read stdin JSON, load config, route, print result."""
    raw = sys.stdin.read()
    try:
        stdin_data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": f"Invalid JSON on stdin: {exc}"}))
        sys.exit(1)

    config_path = os.path.join(ANONYMIZER_DIR, "config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    else:
        config = {}

    result = handle_pretool_use(stdin_data, config)
    if result:
        print(json.dumps(result, ensure_ascii=False))
    # else: exit 0 with no output (approve)


if __name__ == "__main__":
    main()
