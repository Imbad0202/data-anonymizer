import pytest
import json
import os
import tempfile
from learned_terms_manager import LearnedTermsManager
from models import Span

class TestLearnedTermsManager:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "learned_terms.json")

    def test_load_empty(self):
        mgr = LearnedTermsManager(self.path)
        assert mgr.is_confirmed_sensitive("foo") == False
        assert mgr.is_confirmed_safe("foo") == False

    def test_add_sensitive(self):
        mgr = LearnedTermsManager(self.path)
        mgr.add_sensitive("張三")
        mgr.save()
        mgr2 = LearnedTermsManager(self.path)
        assert mgr2.is_confirmed_sensitive("張三") == True

    def test_add_safe(self):
        mgr = LearnedTermsManager(self.path)
        mgr.add_safe("天氣")
        mgr.save()
        mgr2 = LearnedTermsManager(self.path)
        assert mgr2.is_confirmed_safe("天氣") == True

    def test_add_sensitive_removes_from_safe(self):
        mgr = LearnedTermsManager(self.path)
        mgr.add_safe("張三")
        mgr.add_sensitive("張三")
        assert mgr.is_confirmed_sensitive("張三") == True
        assert mgr.is_confirmed_safe("張三") == False

    def test_filter_spans(self):
        mgr = LearnedTermsManager(self.path)
        mgr.add_sensitive("張三")
        mgr.add_safe("天氣")

        spans = [
            Span(0, 2, "張三", "PERSON", "", 0.7, "ner"),     # learned sensitive → keep
            Span(5, 7, "天氣", "PERSON", "", 0.6, "ner"),     # learned safe → drop
            Span(10, 13, "王小明", "PERSON", "", 0.5, "ner"),  # unknown → uncertain
            Span(20, 25, "台北市", "LOCATION", "", 0.9, "ner"), # high confidence → keep
        ]
        kept, uncertain = mgr.filter_spans(spans, confidence_threshold=0.8)
        assert len(kept) == 2  # 張三 (promoted) + 台北市 (high confidence)
        assert any(s.text == "張三" for s in kept)
        assert any(s.text == "台北市" for s in kept)
        assert len(uncertain) == 1
        assert uncertain[0].text == "王小明"
