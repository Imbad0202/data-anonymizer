# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Data Anonymizer.

Two build targets:
  1. Full build — includes NER (PyTorch + ckip-transformers), ~2-3GB
  2. Lite build — regex + custom detectors only, ~150-250MB

Usage:
  Full:  pyinstaller anonymizer.spec
  Lite:  pyinstaller anonymizer.spec -- --lite

The --onedir format is required because Tesseract binaries must be
bundled alongside the executable.
"""

import os
import sys

# Detect --lite flag
lite_mode = '--lite' in sys.argv
if lite_mode:
    sys.argv.remove('--lite')

block_cipher = None

# Base directory — use SPECPATH (set by PyInstaller to the spec file's directory)
# Fall back to current working directory if SPECPATH is not in expected location
_specdir = os.path.dirname(os.path.abspath(SPECPATH))
if os.path.isfile(os.path.join(_specdir, 'gui', 'web_app.py')):
    BASE_DIR = _specdir
else:
    BASE_DIR = os.getcwd()

# Data files to bundle
datas = [
    # OpenCV DNN face detection model
    (os.path.join(BASE_DIR, 'models', 'deploy.prototxt'), 'models'),
    (os.path.join(BASE_DIR, 'models', 'res10_300x300_ssd_iter_140000.caffemodel'), 'models'),
]

# Tesseract OCR — bundled as portable binary (Windows)
# CI workflow downloads and places these in _internal/tesseract/
tesseract_dir = os.path.join(BASE_DIR, '_internal', 'tesseract')
if os.path.isdir(tesseract_dir):
    datas.append((tesseract_dir, 'tesseract'))

# ckip NER model (Full build only — pre-downloaded by CI)
ckip_model_dir = os.path.join(BASE_DIR, 'ckip_models')
if not lite_mode and os.path.isdir(ckip_model_dir):
    datas.append((ckip_model_dir, 'ckip_models'))

# Logo templates directory (if exists)
logo_dir = os.path.join(BASE_DIR, 'logo_templates')
if os.path.isdir(logo_dir):
    datas.append((logo_dir, 'logo_templates'))

# Default config
config_file = os.path.join(BASE_DIR, 'config.json')
if os.path.isfile(config_file):
    datas.append((config_file, '.'))

# Web UI static files and templates
gui_static = os.path.join(BASE_DIR, 'gui', 'static')
if os.path.isdir(gui_static):
    datas.append((gui_static, os.path.join('gui', 'static')))

gui_templates = os.path.join(BASE_DIR, 'gui', 'templates')
if os.path.isdir(gui_templates):
    datas.append((gui_templates, os.path.join('gui', 'templates')))

# Hidden imports
hiddenimports = [
    'PIL',
    'cv2',
    'numpy',
    'pdfplumber',
    'docx',
    'openpyxl',
    'pptx',
    'flask',
]

# Exclude NER dependencies in lite mode
excludes = []
if lite_mode:
    excludes = [
        'torch',
        'transformers',
        'ckip_transformers',
        'tokenizers',
        'huggingface_hub',
        'safetensors',
        'sentencepiece',
        'tqdm',
    ]
else:
    hiddenimports.extend([
        'torch',
        'transformers',
        'ckip_transformers',
    ])

app_name = 'DataAnonymizer' + ('Lite' if lite_mode else '')

a = Analysis(
    [os.path.join(BASE_DIR, 'gui', 'web_app.py')],
    pathex=[BASE_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[os.path.join(BASE_DIR, 'runtime_hook.py')],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # GUI app, no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(BASE_DIR, 'assets', 'icon.ico') if os.path.isfile(os.path.join(BASE_DIR, 'assets', 'icon.ico')) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=app_name,
)
