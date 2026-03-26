"""
test_irreversible.py — Tests for irreversible anonymization mode.

Irreversible mode produces generic labels like [SCHOOL] instead of tokens,
and does NOT create mapping files (compliant with 台灣個資法 去識別化).
"""

import os
import tempfile

import pytest

from mapping_manager import MappingManager


class TestMappingManagerIrreversible:
    """MappingManager in irreversible mode returns labels, not tokens."""

    def test_irreversible_returns_category_label(self):
        mgr = MappingManager(session_id="irrev_test", reversible=False)
        label = mgr.get_or_create_token("國立台灣大學", "SCHOOL")
        assert label == "[SCHOOL]"

    def test_irreversible_same_value_same_label(self):
        mgr = MappingManager(session_id="irrev_test", reversible=False)
        label1 = mgr.get_or_create_token("國立台灣大學", "SCHOOL")
        label2 = mgr.get_or_create_token("國立台灣大學", "SCHOOL")
        assert label1 == label2 == "[SCHOOL]"

    def test_irreversible_different_values_same_category_same_label(self):
        """In irreversible mode, all entities of the same category get the same label."""
        mgr = MappingManager(session_id="irrev_test", reversible=False)
        label1 = mgr.get_or_create_token("國立台灣大學", "SCHOOL")
        label2 = mgr.get_or_create_token("國立清華大學", "SCHOOL")
        assert label1 == label2 == "[SCHOOL]"

    def test_irreversible_no_mapping_stored(self):
        mgr = MappingManager(session_id="irrev_test", reversible=False)
        mgr.get_or_create_token("王小明", "PERSON")
        assert len(mgr._forward) == 0
        assert len(mgr._reverse) == 0

    def test_irreversible_save_creates_no_file(self, tmp_path):
        mgr = MappingManager(
            session_id="irrev_test",
            mappings_dir=str(tmp_path),
            reversible=False,
        )
        mgr.get_or_create_token("王小明", "PERSON")
        mgr.save()
        # No session file should be created
        assert not os.path.exists(os.path.join(str(tmp_path), "session_irrev_test.json"))

    def test_reversible_still_works(self):
        """Ensure reversible=True (default) is unchanged."""
        mgr = MappingManager(session_id="rev_test", reversible=True)
        token = mgr.get_or_create_token("國立台灣大學", "SCHOOL")
        assert token == "__ANON:SCHOOL_001__"
        assert len(mgr._reverse) == 1


class TestAnonymizerIrreversible:
    """Anonymizer with reversible=False produces generic labels."""

    def test_anonymize_text_irreversible(self):
        from anonymizer import Anonymizer

        config = {
            "custom_terms": {"schools": ["國立台灣大學"], "people": ["王小明"]},
            "substring_match": True,
        }
        anon = Anonymizer(config=config, session_id="irrev_anon", use_ner=False, reversible=False)
        result, summary = anon.anonymize_text("國立台灣大學的王小明教授")

        assert "國立台灣大學" not in result
        assert "王小明" not in result
        assert "[SCHOOL]" in result
        assert "[PEOPLE]" in result  # category from CATEGORY_MAP: "people" -> uppercase key
        assert "__ANON:" not in result  # no tokens

    def test_anonymize_text_reversible_default(self):
        from anonymizer import Anonymizer

        config = {
            "custom_terms": {"schools": ["國立台灣大學"]},
            "substring_match": True,
        }
        anon = Anonymizer(config=config, session_id="rev_anon", use_ner=False)
        result, summary = anon.anonymize_text("國立台灣大學的報告")

        assert "__ANON:SCHOOL_001__" in result
        assert "[SCHOOL]" not in result
