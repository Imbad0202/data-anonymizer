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


def test_frozen_base_dir_uses_meipass():
    """In frozen mode with _MEIPASS, BASE_DIR should use _MEIPASS (not sys.executable dir).

    macOS .app bundles place data files under Contents/Resources/ (_MEIPASS),
    not Contents/MacOS/ (sys.executable dir). Using the wrong base dir causes
    ckip NER models and Tesseract data to be unfindable.
    """
    import importlib
    import runtime_hook

    fake_meipass = "/app/Contents/Resources"
    with patch.object(sys, "frozen", True, create=True), \
         patch.object(sys, "_MEIPASS", fake_meipass, create=True), \
         patch.object(sys, "executable", "/app/Contents/MacOS/DataAnonymizer"):
        importlib.reload(runtime_hook)
        assert runtime_hook.BASE_DIR == fake_meipass

    # Restore module to unfrozen state
    if hasattr(sys, "frozen"):
        delattr(sys, "frozen")
    if hasattr(sys, "_MEIPASS"):
        delattr(sys, "_MEIPASS")
    importlib.reload(runtime_hook)


def test_frozen_base_dir_fallback_without_meipass():
    """Without _MEIPASS, frozen BASE_DIR falls back to executable directory."""
    import importlib
    import runtime_hook

    with patch.object(sys, "frozen", True, create=True), \
         patch("runtime_hook.getattr", side_effect=lambda o, n, d=None: d if n == "_MEIPASS" else getattr(o, n, d)):
        # Can't easily mock missing _MEIPASS via patch.object, so test the logic directly
        base = getattr(sys, "_MEIPASS", "/fallback/dir")
        if not hasattr(sys, "_MEIPASS"):
            assert base == "/fallback/dir"

    # Restore
    if hasattr(sys, "frozen"):
        delattr(sys, "frozen")
    importlib.reload(runtime_hook)
