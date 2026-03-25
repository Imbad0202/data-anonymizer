"""
restore.py — PostToolUse hook entry point for Write and Edit tools.

Reads the file written/edited by Claude, checks for __ANON:...__  tokens,
and restores the original values using the session's MappingManager.
"""
import json
import os
import re
import sys

from mapping_manager import MappingManager, TOKEN_PATTERN

# Anonymizer's own directory — never touch these files
_ANONYMIZER_DIR = os.path.expanduser("~/.claude/anonymizer")

# Tools that produce file output we should inspect
_WRITE_TOOLS = {"Write", "Edit"}


def _is_internal_file(file_path: str) -> bool:
    """Return True if the file lives inside the anonymizer project itself."""
    try:
        return os.path.abspath(file_path).startswith(os.path.abspath(_ANONYMIZER_DIR))
    except Exception:
        return False


def handle_post_tool_use(stdin_data: dict, mappings_dir: str = "/tmp/anonymizer") -> None:
    """
    Process a PostToolUse event.

    Parameters
    ----------
    stdin_data : dict
        Parsed JSON from stdin with keys: session_id, tool_name, tool_input.
    mappings_dir : str
        Directory where session mapping files are stored.
    """
    tool_name = stdin_data.get("tool_name", "")

    # Only act on Write and Edit tools
    if tool_name not in _WRITE_TOOLS:
        return

    tool_input = stdin_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path:
        return

    # Never modify anonymizer internal files
    if _is_internal_file(file_path):
        return

    # Read the file content
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, IOError):
        # File unreadable or doesn't exist — nothing to do
        return

    # Quick check: are there any tokens at all?
    if not TOKEN_PATTERN.search(content):
        return

    # Load the mapping for this session and restore
    session_id = stdin_data.get("session_id", "")
    mgr = MappingManager(session_id=session_id, mappings_dir=mappings_dir)
    mgr.load()

    restored = mgr.restore(content)

    # Overwrite the file with de-anonymized content
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(restored)


def main() -> None:
    """Entry point: read JSON from stdin, call handle_post_tool_use, exit 0."""
    raw = sys.stdin.read()
    try:
        stdin_data = json.loads(raw)
    except json.JSONDecodeError:
        # Malformed input — exit silently so the hook doesn't block Claude
        sys.exit(0)

    handle_post_tool_use(stdin_data)
    sys.exit(0)


if __name__ == "__main__":
    main()
