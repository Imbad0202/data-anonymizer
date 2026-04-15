"""
Test platform-aware tesseract binary path resolution.
runtime_hook.py must pick the correct binary name per platform:
- Windows: tesseract.exe
- macOS / Linux: tesseract
"""

import sys
from unittest.mock import patch


def test_tesseract_binary_name_windows():
    """On Windows (win32), binary name is tesseract.exe."""
    with patch.object(sys, "platform", "win32"):
        from runtime_hook import _tesseract_binary_name
        assert _tesseract_binary_name() == "tesseract.exe"


def test_tesseract_binary_name_macos():
    """On macOS (darwin), binary name is tesseract (no extension)."""
    with patch.object(sys, "platform", "darwin"):
        from runtime_hook import _tesseract_binary_name
        assert _tesseract_binary_name() == "tesseract"


def test_tesseract_binary_name_linux():
    """On Linux, binary name is tesseract."""
    with patch.object(sys, "platform", "linux"):
        from runtime_hook import _tesseract_binary_name
        assert _tesseract_binary_name() == "tesseract"


def test_tesseract_subdir_windows():
    """On Windows, subdir is 'tesseract'."""
    with patch.object(sys, "platform", "win32"):
        from runtime_hook import _tesseract_subdir
        assert _tesseract_subdir() == "tesseract"


def test_tesseract_subdir_macos():
    """On macOS, subdir is 'tesseract-macos' to avoid collision."""
    with patch.object(sys, "platform", "darwin"):
        from runtime_hook import _tesseract_subdir
        assert _tesseract_subdir() == "tesseract-macos"
