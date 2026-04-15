# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Data Anonymizer.

Two build targets:
  1. Full build — includes NER (PyTorch + ckip-transformers), ~2-3GB
  2. Lite build — regex + custom detectors only, ~150-250MB

Usage:
  Full:  pyinstaller anonymizer.spec
  Lite:  pyinstaller anonymizer.spec -- --lite

macOS produces a .app bundle via the BUNDLE() block; Windows produces
a onedir tree. On macOS we also set the icns icon and Info.plist.
"""

import os
import sys

# Detect --lite flag
lite_mode = "--lite" in sys.argv
if lite_mode:
    sys.argv.remove("--lite")

IS_MACOS = sys.platform == "darwin"

block_cipher = None

# Base directory — use SPECPATH (set by PyInstaller to the spec file's directory)
_specdir = os.path.dirname(os.path.abspath(SPECPATH))
if os.path.isfile(os.path.join(_specdir, "gui", "web_app.py")):
    BASE_DIR = _specdir
else:
    BASE_DIR = os.getcwd()

# Version (for macOS Info.plist) — read textually to avoid sys.path side effects
import re as _re
_updater_path = os.path.join(BASE_DIR, "updater.py")
APP_VERSION = "0.0.0"
if os.path.isfile(_updater_path):
    with open(_updater_path, encoding="utf-8") as _f:
        _m = _re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', _f.read(), _re.M)
    if _m:
        APP_VERSION = _m.group(1)
    else:
        sys.stderr.write("WARN: could not parse __version__ from updater.py; using 0.0.0\n")
del _updater_path

# Data files to bundle
datas = [
    (os.path.join(BASE_DIR, "models", "deploy.prototxt"), "models"),
    (os.path.join(BASE_DIR, "models", "res10_300x300_ssd_iter_140000.caffemodel"), "models"),
]

# Tesseract OCR — bundle path differs per platform
tesseract_subdir = "tesseract-macos" if IS_MACOS else "tesseract"
tesseract_dir = os.path.join(BASE_DIR, "_internal", tesseract_subdir)
if os.path.isdir(tesseract_dir):
    datas.append((tesseract_dir, tesseract_subdir))

# ckip NER model (Full build only — pre-downloaded by CI or build script)
ckip_model_dir = os.path.join(BASE_DIR, "ckip_models")
if not lite_mode and os.path.isdir(ckip_model_dir):
    datas.append((ckip_model_dir, "ckip_models"))

# Logo templates directory (if exists)
logo_dir = os.path.join(BASE_DIR, "logo_templates")
if os.path.isdir(logo_dir):
    datas.append((logo_dir, "logo_templates"))

# Default config
config_file = os.path.join(BASE_DIR, "config.json")
if os.path.isfile(config_file):
    datas.append((config_file, "."))

# Web UI static files and templates
gui_static = os.path.join(BASE_DIR, "gui", "static")
if os.path.isdir(gui_static):
    datas.append((gui_static, os.path.join("gui", "static")))

gui_templates = os.path.join(BASE_DIR, "gui", "templates")
if os.path.isdir(gui_templates):
    datas.append((gui_templates, os.path.join("gui", "templates")))

# Hidden imports
hiddenimports = [
    "PIL",
    "cv2",
    "numpy",
    "pdfplumber",
    "docx",
    "openpyxl",
    "pptx",
    "flask",
]

# Exclude NER dependencies in lite mode
excludes = []
if lite_mode:
    excludes = [
        "torch",
        "transformers",
        "ckip_transformers",
        "tokenizers",
        "huggingface_hub",
        "safetensors",
        "sentencepiece",
        "tqdm",
    ]
else:
    hiddenimports.extend(["torch", "transformers", "ckip_transformers"])

app_name = "DataAnonymizer" + ("Lite" if lite_mode else "")

# Icon selection per platform
ico_path = os.path.join(BASE_DIR, "assets", "icon.ico")
icns_path = os.path.join(BASE_DIR, "assets", "icon.icns")
if IS_MACOS and os.path.isfile(icns_path):
    icon_path = icns_path
elif os.path.isfile(ico_path):
    icon_path = ico_path
else:
    icon_path = None


a = Analysis(
    [os.path.join(BASE_DIR, "gui", "web_app.py")],
    pathex=[BASE_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[os.path.join(BASE_DIR, "runtime_hook.py")],
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
    upx=not IS_MACOS,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=not IS_MACOS,
    upx_exclude=[],
    name=app_name,
)

# macOS .app bundle
if IS_MACOS:
    bundle_id_suffix = ".lite" if lite_mode else ""
    app = BUNDLE(
        coll,
        name=f"{app_name}.app",
        icon=icon_path,
        bundle_identifier=f"tw.imbad.dataanonymizer{bundle_id_suffix}",
        info_plist={
            "CFBundleShortVersionString": APP_VERSION,
            "CFBundleVersion": APP_VERSION,
            "CFBundleName": "Anonymizer" + (" Lite" if lite_mode else ""),
            "CFBundleDisplayName": "Data Anonymizer" + (" Lite" if lite_mode else ""),
            "NSHumanReadableCopyright": "© 2026 CHENG-I WU. CC BY-NC 4.0.",
            "NSHighResolutionCapable": True,
            "LSUIElement": False,
            "LSMinimumSystemVersion": "12.0",
            "NSRequiresAquaSystemAppearance": False,
        },
    )
