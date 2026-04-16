"""
PyInstaller runtime hook — sets up environment for bundled dependencies.

Configures:
- TESSDATA_PREFIX for bundled Tesseract OCR
- OpenCV DNN model paths
- HuggingFace offline mode + local ckip NER model path
"""

import os
import sys


def _tesseract_binary_name() -> str:
    """Platform-specific tesseract executable filename."""
    if sys.platform == "win32":
        return "tesseract.exe"
    return "tesseract"


def _tesseract_subdir() -> str:
    """Bundle subdirectory for tesseract binaries.

    Separate per-platform so a cross-bundled artifact cannot
    accidentally contain the wrong architecture's binary.
    """
    if sys.platform == "darwin":
        return "tesseract-macos"
    return "tesseract"


# When frozen (PyInstaller), _MEIPASS points to the data directory:
# - onefile: temp extraction dir
# - onedir macOS .app: Contents/Resources/
# - onedir Windows/Linux: same as executable dir
# Fall back to executable dir for compatibility with older PyInstaller builds.
if getattr(sys, "frozen", False):
    BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# Set Tesseract data path
tesseract_dir = os.path.join(BASE_DIR, _tesseract_subdir())
tessdata_dir = os.path.join(tesseract_dir, "tessdata")
if os.path.isdir(tessdata_dir):
    os.environ["TESSDATA_PREFIX"] = tessdata_dir


# Set Tesseract binary path (cross-platform)
tesseract_bin = os.path.join(tesseract_dir, _tesseract_binary_name())
if os.path.isfile(tesseract_bin):
    try:
        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = tesseract_bin
    except ImportError:
        pass


# ckip NER model — use bundled model, block network downloads in frozen builds
ckip_model_dir = os.path.join(BASE_DIR, "ckip_models", "bert-base-chinese-ner")
if os.path.isdir(ckip_model_dir):
    os.environ["CKIP_MODEL_DIR"] = ckip_model_dir
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
