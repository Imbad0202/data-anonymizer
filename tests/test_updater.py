"""Tests for updater.py — GitHub Releases update checker."""

import json
from unittest.mock import patch, MagicMock

import pytest

from updater import _is_newer, check_for_update


# ---------------------------------------------------------------------------
# Version comparison
# ---------------------------------------------------------------------------

class TestIsNewer:
    def test_newer_patch(self):
        assert _is_newer("2.0.1", "2.0.0") is True

    def test_newer_minor(self):
        assert _is_newer("2.1.0", "2.0.0") is True

    def test_newer_major(self):
        assert _is_newer("3.0.0", "2.0.0") is True

    def test_same_version(self):
        assert _is_newer("2.0.0", "2.0.0") is False

    def test_older_version(self):
        assert _is_newer("1.9.0", "2.0.0") is False

    def test_invalid_version(self):
        assert _is_newer("abc", "2.0.0") is False

    def test_empty_string(self):
        assert _is_newer("", "2.0.0") is False


# ---------------------------------------------------------------------------
# check_for_update
# ---------------------------------------------------------------------------

class TestCheckForUpdate:
    def test_update_available(self):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "tag_name": "v3.0.0",
            "html_url": "https://github.com/Imbad0202/data-anonymizer/releases/tag/v3.0.0",
        }).encode()

        with patch("updater.urllib.request.urlopen", return_value=mock_response):
            has_update, version, url = check_for_update("2.0.0")

        assert has_update is True
        assert version == "3.0.0"
        assert "releases" in url

    def test_no_update(self):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "tag_name": "v2.0.0",
            "html_url": "https://github.com/test/repo/releases/tag/v2.0.0",
        }).encode()

        with patch("updater.urllib.request.urlopen", return_value=mock_response):
            has_update, version, url = check_for_update("2.0.0")

        assert has_update is False

    def test_network_error_silent(self):
        with patch("updater.urllib.request.urlopen", side_effect=Exception("timeout")):
            has_update, version, url = check_for_update("2.0.0")

        assert has_update is False
        assert version == ""
        assert url == ""

    def test_uses_default_version(self):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "tag_name": "v99.0.0",
            "html_url": "https://example.com",
        }).encode()

        with patch("updater.urllib.request.urlopen", return_value=mock_response):
            has_update, _, _ = check_for_update()  # uses __version__

        assert has_update is True

    def test_tag_without_v_prefix(self):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "tag_name": "3.0.0",
            "html_url": "https://example.com",
        }).encode()

        with patch("updater.urllib.request.urlopen", return_value=mock_response):
            has_update, version, _ = check_for_update("2.0.0")

        assert has_update is True
        assert version == "3.0.0"
