import pytest
import os
import tempfile
from restore import handle_post_tool_use
from mapping_manager import MappingManager

class TestRestore:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.mgr = MappingManager(session_id="test_restore", mappings_dir=self.tmpdir)
        self.mgr.get_or_create_token("國立OO大學", "SCHOOL")
        self.mgr.get_or_create_token("test@test.com", "EMAIL")
        self.mgr.save()

    def test_restore_written_file(self):
        outfile = os.path.join(self.tmpdir, "output.md")
        with open(outfile, 'w') as f:
            f.write("# Report\n__ANON:SCHOOL_001__ 的 email 是 __ANON:EMAIL_001__")
        stdin_data = {"session_id": "test_restore", "tool_name": "Write", "tool_input": {"file_path": outfile}}
        handle_post_tool_use(stdin_data, mappings_dir=self.tmpdir)
        with open(outfile, 'r') as f:
            content = f.read()
        assert "國立OO大學" in content
        assert "test@test.com" in content
        assert "__ANON:" not in content

    def test_no_tokens_no_change(self):
        outfile = os.path.join(self.tmpdir, "clean.md")
        original = "No tokens here"
        with open(outfile, 'w') as f:
            f.write(original)
        stdin_data = {"session_id": "test_restore", "tool_name": "Write", "tool_input": {"file_path": outfile}}
        handle_post_tool_use(stdin_data, mappings_dir=self.tmpdir)
        with open(outfile, 'r') as f:
            assert f.read() == original

    def test_edit_tool_also_restores(self):
        outfile = os.path.join(self.tmpdir, "edited.md")
        with open(outfile, 'w') as f:
            f.write("Edited by __ANON:SCHOOL_001__")
        stdin_data = {"session_id": "test_restore", "tool_name": "Edit", "tool_input": {"file_path": outfile}}
        handle_post_tool_use(stdin_data, mappings_dir=self.tmpdir)
        with open(outfile, 'r') as f:
            assert "國立OO大學" in f.read()

    def test_ignores_non_write_tools(self):
        stdin_data = {"session_id": "test_restore", "tool_name": "Read", "tool_input": {"file_path": "/tmp/whatever"}}
        handle_post_tool_use(stdin_data, mappings_dir=self.tmpdir)  # should not crash
