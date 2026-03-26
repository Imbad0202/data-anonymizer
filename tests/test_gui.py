"""Tests for GUI components — logic tests only, no display required.

These tests verify the preview panel's data processing and the app's
file management logic without actually rendering windows.
"""

import os
import re
from unittest.mock import MagicMock, patch

import pytest

# Skip all tests if tkinter is not available (CI environments)
tk = pytest.importorskip("tkinter")


# ---------------------------------------------------------------------------
# Preview panel highlight logic
# ---------------------------------------------------------------------------

class TestPreviewHighlighting:
    """Test the token/label highlighting patterns used by PreviewPanel."""

    def test_token_pattern_matches(self):
        pattern = r'__ANON:[A-Z]+_\d+__'
        text = "張三 is replaced by __ANON:PERSON_001__"
        matches = re.findall(pattern, text)
        assert matches == ["__ANON:PERSON_001__"]

    def test_label_pattern_matches(self):
        pattern = r'\[[A-Z_]+\]'
        text = "Name: [PERSON], School: [SCHOOL]"
        matches = re.findall(pattern, text)
        assert matches == ["[PERSON]", "[SCHOOL]"]

    def test_no_false_positives(self):
        pattern = r'__ANON:[A-Z]+_\d+__'
        text = "This is normal text with [brackets] and __underscores__"
        matches = re.findall(pattern, text)
        assert matches == []


# ---------------------------------------------------------------------------
# App file management logic (no GUI needed)
# ---------------------------------------------------------------------------

class TestFileManagement:
    def test_image_extension_detection(self):
        from parsers.image_parser import ImageParser
        exts = set(ImageParser.EXTENSIONS)
        assert ".jpg" in exts
        assert ".png" in exts
        assert ".txt" not in exts

    def test_get_parser_for_supported_types(self):
        from anonymizer import get_parser
        assert get_parser("test.txt") is not None
        assert get_parser("test.docx") is not None
        assert get_parser("test.pdf") is not None

    def test_get_parser_for_unsupported(self):
        from anonymizer import get_parser
        assert get_parser("test.xyz") is None
        assert get_parser("test.exe") is None
