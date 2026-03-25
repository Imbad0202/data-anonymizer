import pytest
import json
import os
import tempfile
from mapping_manager import MappingManager

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
