import pytest
import json
import os
import tempfile
from mapping_manager import MappingManager


class TestPersistentMapping:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.persistent_path = os.path.join(self.tmpdir, "persistent.json")

    def test_persistent_mapping_carries_across_sessions(self):
        mgr1 = MappingManager(session_id="s1", mappings_dir=self.tmpdir, persistent_path=self.persistent_path)
        t1 = mgr1.get_or_create_token("張三", "PERSON")
        mgr1.save(persist=True)

        mgr2 = MappingManager(session_id="s2", mappings_dir=self.tmpdir, persistent_path=self.persistent_path)
        t2 = mgr2.get_or_create_token("張三", "PERSON")
        assert t2 == t1

    def test_persistent_disabled_by_default(self):
        mgr1 = MappingManager(session_id="s1", mappings_dir=self.tmpdir)
        mgr1.get_or_create_token("張三", "PERSON")
        mgr1.save()

        mgr2 = MappingManager(session_id="s2", mappings_dir=self.tmpdir)
        t2 = mgr2.get_or_create_token("張三", "PERSON")
        assert t2 == "__ANON:PERSON_001__"  # fresh counter, no persistence

class TestMappingManager:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.mgr = MappingManager(session_id="test123", mappings_dir=self.tmpdir)

    def test_get_or_create_token_new_entity(self):
        token = self.mgr.get_or_create_token("張三", "PERSON")
        assert token == "__ANON:PERSON_001__"

    def test_get_or_create_token_same_entity_same_token(self):
        t1 = self.mgr.get_or_create_token("張三", "PERSON")
        t2 = self.mgr.get_or_create_token("張三", "PERSON")
        assert t1 == t2

    def test_get_or_create_token_different_entities(self):
        t1 = self.mgr.get_or_create_token("張三", "PERSON")
        t2 = self.mgr.get_or_create_token("李四", "PERSON")
        assert t1 == "__ANON:PERSON_001__"
        assert t2 == "__ANON:PERSON_002__"

    def test_different_categories(self):
        t1 = self.mgr.get_or_create_token("國立OO大學", "SCHOOL")
        t2 = self.mgr.get_or_create_token("test@test.com", "EMAIL")
        assert t1 == "__ANON:SCHOOL_001__"
        assert t2 == "__ANON:EMAIL_001__"

    def test_save_and_load(self):
        self.mgr.get_or_create_token("張三", "PERSON")
        self.mgr.save()
        mgr2 = MappingManager(session_id="test123", mappings_dir=self.tmpdir)
        mgr2.load()
        assert mgr2.get_or_create_token("張三", "PERSON") == "__ANON:PERSON_001__"

    def test_reverse_mapping(self):
        self.mgr.get_or_create_token("張三", "PERSON")
        self.mgr.get_or_create_token("test@test.com", "EMAIL")
        text = "Hello __ANON:PERSON_001__, your email is __ANON:EMAIL_001__"
        restored = self.mgr.restore(text)
        assert restored == "Hello 張三, your email is test@test.com"

    def test_restore_no_tokens(self):
        text = "No tokens here"
        assert self.mgr.restore(text) == "No tokens here"

    def test_file_path_mapping(self):
        anon_path = self.mgr.register_file_path("/Users/imbad/Documents/report.docx")
        assert anon_path.startswith("/tmp/anonymizer/anonymized_")
        assert self.mgr.get_original_path(anon_path) == "/Users/imbad/Documents/report.docx"
