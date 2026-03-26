"""
PyInstaller runtime hook — sets up environment for bundled dependencies.

Configures:
- TESSDATA_PREFIX for bundled Tesseract OCR
- OpenCV DNN model paths
"""

import os
import sys

# When frozen (PyInstaller), _MEIPASS points to the temp extraction dir (onefile)
# or the app directory (onedir). For onedir, use the executable's directory.
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Set Tesseract data path
tesseract_dir = os.path.join(BASE_DIR, 'tesseract')
tessdata_dir = os.path.join(tesseract_dir, 'tessdata')
if os.path.isdir(tessdata_dir):
    os.environ['TESSDATA_PREFIX'] = tessdata_dir

# Set Tesseract binary path (Windows)
tesseract_exe = os.path.join(tesseract_dir, 'tesseract.exe')
if os.path.isfile(tesseract_exe):
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = tesseract_exe
    except ImportError:
        pass
