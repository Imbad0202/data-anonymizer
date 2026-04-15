# macOS Portable Build Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship signed, notarized macOS arm64 Portable zip for Data Anonymizer (Lite + Full), matching Windows Portable distribution.

**Architecture:** PyInstaller onedir → codesign (hardened runtime, minimal entitlements) → notarize (App Store Connect API) → staple → ditto zip. Local-first validation, then GitHub Actions for release automation.

**Tech Stack:** Python 3.11 (arm64 venv), PyInstaller, codesign, xcrun notarytool, ditto, Homebrew (tesseract + dylibbundler), install_name_tool, GitHub Actions (macos-14 runner).

**Spec:** `docs/superpowers/specs/2026-04-15-macos-portable-build-design.md`

---

## File Structure

New files (created by plan):

- `build-macos.sh` — local build orchestrator (bash)
- `entitlements.plist` — notarization entitlements
- `scripts/bundle-tesseract-macos.sh` — Tesseract + dylib bundling helper
- `assets/icon.icns` — macOS app icon (derived from existing icon)
- `.github/workflows/build-macos.yml` — CI automation (Phase 3)
- `docs/MACOS_FIRST_RUN.md` — user guide (Traditional Chinese)

Modified files:

- `anonymizer.spec` — add macOS platform branch (BUNDLE block, icns icon, tesseract path)
- `runtime_hook.py` — add macOS branch for tesseract binary path
- `README.md` — add macOS download section

Test files:

- `tests/test_runtime_hook_platform.py` — new, unit tests for platform-aware tesseract path resolution

---

## Phase 0 — Environment Prerequisites

### Task 0.1: Verify build prerequisites

**Files:**
- No file changes (verification only)

- [ ] **Step 1: Verify Xcode Command Line Tools**

Run: `xcode-select -p`
Expected output: `/Applications/Xcode.app/Contents/Developer` or `/Library/Developer/CommandLineTools`

If it prints a path, continue. If it errors, run `xcode-select --install` in a separate terminal (interactive, not this session).

- [ ] **Step 2: Verify Homebrew**

Run: `which brew && brew --version`
Expected: `/opt/homebrew/bin/brew` and version string

- [ ] **Step 3: Verify Python 3.11 arm64**

Run: `python3.11 -c "import sys, platform; print(sys.version); print('arch:', platform.machine())"`
Expected: Python 3.11.x and `arch: arm64`

- [ ] **Step 4: Verify Developer ID certificate in Keychain**

Run: `security find-identity -v -p codesigning | grep "Developer ID Application"`
Expected: line like `... "Developer ID Application: CHENG-I WU (2798YNATMH)"`

- [ ] **Step 5: Verify notarytool API key works**

Run:
```bash
xcrun notarytool history \
  --key ~/.private_keys/AuthKey_WXNK385FUP.p8 \
  --key-id WXNK385FUP \
  --issuer 237d9fe4-3ec6-47f9-b0c1-36c530d812b5
```
Expected: Either submission list or `No submission history.` (both mean auth works)

- [ ] **Step 6: Install tesseract and dylibbundler via Homebrew**

Run: `brew install tesseract dylibbundler`
Expected: tesseract 5.x + dylibbundler installed. Verify:
```bash
which tesseract && tesseract --version 2>&1 | head -2
which dylibbundler
```

Note: `tesseract` bottle provides only `eng`/`osd` data. We'll download `chi_tra.traineddata` separately in build.

- [ ] **Step 7: Commit prerequisites docs**

No code commit yet — Phase 0 is verification only. Record outcome in task tracker.

---

## Phase 1 — Core Build Files (No Runtime Yet)

### Task 1.1: Add entitlements.plist

**Files:**
- Create: `entitlements.plist`

- [ ] **Step 1: Write entitlements.plist**

Create `entitlements.plist` with exactly this content:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.cs.allow-jit</key>
    <true/>
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
    <true/>
</dict>
</plist>
```

- [ ] **Step 2: Validate plist syntax**

Run: `plutil -lint entitlements.plist`
Expected: `entitlements.plist: OK`

- [ ] **Step 3: Commit**

```bash
git add entitlements.plist
git commit -m "Add macOS entitlements.plist for hardened runtime

JIT + unsigned-executable-memory are the minimum required for
Python bundled via PyInstaller (and PyTorch in the Full build)."
```

---

### Task 1.2: Generate icon.icns from existing icon

**Files:**
- Create: `assets/icon.icns`
- Create: `assets/` directory if missing

- [ ] **Step 1: Check existing icons**

Run: `ls -la assets/ 2>/dev/null || echo "assets/ does not exist"`

Current state:
- `assets/icon.ico` exists (per Windows build) — **verify this first**:
  ```bash
  find . -name "icon.ico" -not -path "./.venv*" -not -path "./dist*" -not -path "./build*"
  ```

If no source image exists at all, create a simple placeholder:
```bash
mkdir -p assets
# Use any 1024x1024 PNG as source. If none exists:
python3.11 -c "
from PIL import Image, ImageDraw
img = Image.new('RGB', (1024, 1024), '#14b8a6')
d = ImageDraw.Draw(img)
d.text((350, 420), 'DA', fill='white')
img.save('assets/icon-source.png')
"
```

If `icon.ico` exists, extract the largest frame as PNG:
```bash
python3.11 -c "
from PIL import Image
img = Image.open('assets/icon.ico')
# Pick largest frame
largest = max(img.ico.sizes()) if hasattr(img, 'ico') else (256, 256)
img.size = largest
img.save('assets/icon-source.png')
"
```

- [ ] **Step 2: Build .icns using macOS iconutil**

```bash
mkdir -p /tmp/icon.iconset

for size in 16 32 64 128 256 512 1024; do
  python3.11 -c "
from PIL import Image
img = Image.open('assets/icon-source.png').convert('RGBA')
img.resize(($size, $size), Image.LANCZOS).save('/tmp/icon.iconset/icon_${size}x${size}.png')
"
done

# Retina variants (@2x)
for size in 16 32 128 256 512; do
  double=$((size * 2))
  python3.11 -c "
from PIL import Image
img = Image.open('assets/icon-source.png').convert('RGBA')
img.resize(($double, $double), Image.LANCZOS).save('/tmp/icon.iconset/icon_${size}x${size}@2x.png')
"
done

iconutil -c icns /tmp/icon.iconset -o assets/icon.icns
rm -rf /tmp/icon.iconset
```

- [ ] **Step 3: Verify icns**

Run: `file assets/icon.icns`
Expected: `assets/icon.icns: Mac OS X icon`

- [ ] **Step 4: Commit**

```bash
git add assets/icon.icns assets/icon-source.png
git commit -m "Add macOS .icns app icon

Derived from existing Windows .ico (or placeholder if none).
Generated via iconutil with standard Retina variants."
```

---

### Task 1.3: Unit test platform-aware tesseract path resolution

**Files:**
- Create: `tests/test_runtime_hook_platform.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_runtime_hook_platform.py`:

```python
"""
Test platform-aware tesseract binary path resolution.
runtime_hook.py must pick the correct binary name per platform:
- Windows: tesseract.exe
- macOS / Linux: tesseract
"""

import os
import sys
import tempfile
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/.claude/anonymizer && .venv/bin/python -m pytest tests/test_runtime_hook_platform.py -v`
Expected: FAIL — `ImportError: cannot import name '_tesseract_binary_name'` (functions don't exist yet)

Note: `runtime_hook.py` is imported directly — no need to invoke PyInstaller machinery.

- [ ] **Step 3: Commit the failing test**

```bash
git add tests/test_runtime_hook_platform.py
git commit -m "Add failing tests for platform-aware tesseract path

Red phase: functions don't exist yet. Next task implements them."
```

---

### Task 1.4: Implement platform-aware paths in runtime_hook

**Files:**
- Modify: `runtime_hook.py`

- [ ] **Step 1: Rewrite runtime_hook.py with platform helpers**

Replace entire contents of `runtime_hook.py`:

```python
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


# When frozen (PyInstaller), _MEIPASS points to the temp extraction dir (onefile)
# or the app directory (onedir). For onedir, use the executable's directory.
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
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
```

- [ ] **Step 2: Run the unit tests**

Run: `cd ~/.claude/anonymizer && .venv/bin/python -m pytest tests/test_runtime_hook_platform.py -v`
Expected: 5 tests PASS

- [ ] **Step 3: Run full suite to catch regressions**

Run: `cd ~/.claude/anonymizer && .venv/bin/python -m pytest -x -q 2>&1 | tail -20`
Expected: All 175+ tests pass (Windows hard-coded behaviour is preserved because `sys.platform == 'win32'` path still returns `tesseract.exe` + `tesseract`).

- [ ] **Step 4: Commit**

```bash
git add runtime_hook.py
git commit -m "Make runtime_hook tesseract path platform-aware

Extract binary name + subdir into helpers. macOS uses
'tesseract-macos/tesseract'; Windows keeps 'tesseract/tesseract.exe'.
Bundle subdirs are separate to avoid cross-platform collision."
```

---

### Task 1.5: Extend anonymizer.spec for macOS (datas + BUNDLE)

**Files:**
- Modify: `anonymizer.spec`

- [ ] **Step 1: Update spec file**

Replace contents of `anonymizer.spec` with:

```python
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

# Version (for macOS Info.plist)
sys.path.insert(0, BASE_DIR)
try:
    from updater import __version__ as APP_VERSION
except Exception:
    APP_VERSION = "0.0.0"

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
    upx=not IS_MACOS,   # UPX causes issues with codesign on macOS
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,  # we sign manually in build-macos.sh for control
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
            "NSHumanReadableCopyright": "© 2026 CHENG-I WU. CC BY-NC 4.0.",
            "NSHighResolutionCapable": True,
            "LSUIElement": False,
            "LSMinimumSystemVersion": "12.0",
            "NSRequiresAquaSystemAppearance": False,
        },
    )
```

- [ ] **Step 2: Syntax check the spec**

Run: `cd ~/.claude/anonymizer && python3.11 -c "exec(open('anonymizer.spec').read(), {'__name__': '__main__', 'SPECPATH': '.', 'Analysis': type('A', (), {'__init__': lambda self, *a, **k: None, 'pure': [], 'zipped_data': None, 'scripts': [], 'binaries': [], 'zipfiles': [], 'datas': []}), 'PYZ': lambda *a, **k: None, 'EXE': lambda *a, **k: None, 'COLLECT': lambda *a, **k: None, 'BUNDLE': lambda *a, **k: None})" 2>&1 | tail -5`

This is a light smoke test (spec files normally only run inside PyInstaller). If it prints nothing and exits 0 the syntax is valid; errors mean fix before commit.

- [ ] **Step 3: Commit**

```bash
git add anonymizer.spec
git commit -m "Extend anonymizer.spec for macOS build

- Platform-aware tesseract bundle subdir
- Read version from updater.__version__ for Info.plist
- BUNDLE block for .app output on darwin
- Bundle identifier tw.imbad.dataanonymizer (+ .lite suffix)
- Disable UPX on macOS (conflicts with codesign)
- Prefer .icns over .ico on macOS when both exist"
```

---

## Phase 2 — Build Scripts (Lite variant end-to-end)

### Task 2.1: Tesseract bundling helper script

**Files:**
- Create: `scripts/bundle-tesseract-macos.sh`

- [ ] **Step 1: Write the script**

Create `scripts/bundle-tesseract-macos.sh`:

```bash
#!/usr/bin/env bash
# bundle-tesseract-macos.sh
#
# Copies the Homebrew tesseract binary and all its dylib dependencies
# into _internal/tesseract-macos/, rewriting dylib paths with
# install_name_tool so the bundle is self-contained.
#
# Requires: brew, dylibbundler, install_name_tool (Xcode CLT).
#
# Output layout:
#   _internal/tesseract-macos/
#     tesseract                  # executable
#     libs/*.dylib               # bundled dependencies
#     tessdata/{eng,osd,chi_tra}.traineddata

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="${REPO_ROOT}/_internal/tesseract-macos"
TESSDATA_DIR="${OUT_DIR}/tessdata"
LIBS_DIR="${OUT_DIR}/libs"

if ! command -v tesseract >/dev/null 2>&1; then
  echo "tesseract not found. Run: brew install tesseract" >&2
  exit 1
fi
if ! command -v dylibbundler >/dev/null 2>&1; then
  echo "dylibbundler not found. Run: brew install dylibbundler" >&2
  exit 1
fi

rm -rf "${OUT_DIR}"
mkdir -p "${TESSDATA_DIR}" "${LIBS_DIR}"

# 1. Copy tesseract binary (resolve symlink; brew binary is usually a shim)
TESSERACT_BIN="$(readlink -f "$(command -v tesseract)" 2>/dev/null || greadlink -f "$(command -v tesseract)" 2>/dev/null || command -v tesseract)"
cp -p "${TESSERACT_BIN}" "${OUT_DIR}/tesseract"
chmod +x "${OUT_DIR}/tesseract"

# 2. Use dylibbundler to pull all deps into libs/ and rewrite @rpath
#    -x: fix the binary
#    -b: bundle dependencies
#    -d: destination lib dir
#    -p: rpath prefix injected into binary (@executable_path/libs)
#    -cd: create destination dir
#    -of: overwrite files
dylibbundler \
  -x "${OUT_DIR}/tesseract" \
  -b \
  -d "${LIBS_DIR}" \
  -p "@executable_path/libs/" \
  -cd \
  -of

# 3. Verify: no absolute /opt/homebrew paths left in binary or its libs
echo "Checking for leftover /opt/homebrew references..."
for f in "${OUT_DIR}/tesseract" "${LIBS_DIR}"/*.dylib; do
  [[ -f "$f" ]] || continue
  if otool -L "$f" 2>/dev/null | grep -q "/opt/homebrew"; then
    echo "FAIL: $f still references /opt/homebrew:" >&2
    otool -L "$f" | grep "/opt/homebrew" >&2
    exit 1
  fi
done

# 4. tessdata (tesseract bottle ships eng + osd only; we also need chi_tra)
BREW_PREFIX="$(brew --prefix tesseract)"
cp "${BREW_PREFIX}/share/tessdata/eng.traineddata" "${TESSDATA_DIR}/"
cp "${BREW_PREFIX}/share/tessdata/osd.traineddata" "${TESSDATA_DIR}/"

CHI_TRA_URL="https://github.com/tesseract-ocr/tessdata_best/raw/main/chi_tra.traineddata"
curl -fsSL "${CHI_TRA_URL}" -o "${TESSDATA_DIR}/chi_tra.traineddata"

# 5. Smoke test: run bundled tesseract on a throwaway test image
TEST_IMG="$(mktemp -t tesseract_test.XXXXXX).png"
python3.11 -c "
from PIL import Image, ImageDraw, ImageFont
img = Image.new('RGB', (300, 80), 'white')
d = ImageDraw.Draw(img)
d.text((10, 20), 'Hello 123', fill='black')
img.save('${TEST_IMG}')
"

TESSDATA_PREFIX="${TESSDATA_DIR}" "${OUT_DIR}/tesseract" "${TEST_IMG}" - -l eng 2>&1 | head -5
rm -f "${TEST_IMG}"

echo "Tesseract bundled successfully at: ${OUT_DIR}"
du -sh "${OUT_DIR}"
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/bundle-tesseract-macos.sh
```

- [ ] **Step 3: Run the script and inspect output**

Run: `scripts/bundle-tesseract-macos.sh`
Expected:
- No "FAIL" messages
- Final line prints `Tesseract bundled successfully at: ...`
- `_internal/tesseract-macos/` exists with `tesseract`, `libs/*.dylib`, `tessdata/{eng,osd,chi_tra}.traineddata`
- Smoke test prints recognizable text from the test image

Verify no homebrew leakage:
```bash
otool -L _internal/tesseract-macos/tesseract | grep -c "/opt/homebrew" || echo "0 (good)"
```
Expected: `0 (good)`

- [ ] **Step 4: Add _internal to .gitignore**

```bash
grep -qxF "_internal/" .gitignore || echo "_internal/" >> .gitignore
```

- [ ] **Step 5: Commit**

```bash
git add scripts/bundle-tesseract-macos.sh .gitignore
git commit -m "Add macOS tesseract bundling script

Uses dylibbundler to pull all Homebrew dylib deps into
_internal/tesseract-macos/libs/ with @executable_path rpath.
Downloads chi_tra.traineddata from tessdata_best upstream.
Includes a smoke test to verify OCR works after bundling."
```

---

### Task 2.2: Main build script (Lite-only initially)

**Files:**
- Create: `build-macos.sh`

- [ ] **Step 1: Write the script**

Create `build-macos.sh`:

```bash
#!/usr/bin/env bash
# build-macos.sh [lite|full]
#
# End-to-end macOS Portable zip builder for Data Anonymizer.
# Phases: venv -> deps -> assets -> pyinstaller -> codesign -> notarize -> staple -> zip.
#
# Required environment:
#   APPLE_SIGN_IDENTITY     e.g. "Developer ID Application: CHENG-I WU (2798YNATMH)"
#   APPLE_NOTARY_KEY        path to App Store Connect API .p8 file
#   APPLE_NOTARY_KEY_ID     10-char key ID
#   APPLE_NOTARY_ISSUER     issuer UUID
#
# Optional:
#   SKIP_NOTARIZE=1         build + sign only, skip notarize/staple/final zip rename

set -euo pipefail

VARIANT="${1:-lite}"
case "${VARIANT}" in
  lite)
    APP_NAME="DataAnonymizerLite"
    SPEC_FLAG="--lite"
    INCLUDE_NER=false
    ;;
  full)
    APP_NAME="DataAnonymizer"
    SPEC_FLAG=""
    INCLUDE_NER=true
    ;;
  *)
    echo "Usage: $0 [lite|full]" >&2
    exit 1
    ;;
esac

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "${REPO_ROOT}"

# Read version from updater.__version__ without full package import
VERSION="$(python3.11 -c 'import re,pathlib;print(re.search(r"__version__\s*=\s*[\x27\x22]([^\x27\x22]+)", pathlib.Path("updater.py").read_text()).group(1))')"
ZIP_NAME="${APP_NAME}-${VERSION}-macOS-arm64.zip"

# Validate env unless skipping
if [[ "${SKIP_NOTARIZE:-0}" != "1" ]]; then
  : "${APPLE_SIGN_IDENTITY:?required}"
  : "${APPLE_NOTARY_KEY:?required}"
  : "${APPLE_NOTARY_KEY_ID:?required}"
  : "${APPLE_NOTARY_ISSUER:?required}"
  [[ -f "${APPLE_NOTARY_KEY}" ]] || { echo "notary key not found: ${APPLE_NOTARY_KEY}" >&2; exit 1; }
else
  : "${APPLE_SIGN_IDENTITY:?required even when skipping notarize (we still sign)}"
fi

echo "=== Phase 1: Clean + venv ==="
rm -rf dist build .venv-build ckip_models
python3.11 -m venv .venv-build
source .venv-build/bin/activate
pip install --upgrade pip pyinstaller >/dev/null
pip install -r requirements.txt >/dev/null
if [[ "${INCLUDE_NER}" != "true" ]]; then
  pip uninstall -y torch transformers ckip-transformers tokenizers safetensors sentencepiece huggingface_hub 2>/dev/null || true
fi

echo "=== Phase 2: OpenCV face model ==="
mkdir -p models
[[ -f models/deploy.prototxt ]] || curl -fsSL \
  "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt" \
  -o models/deploy.prototxt
[[ -f models/res10_300x300_ssd_iter_140000.caffemodel ]] || curl -fsSL \
  "https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel" \
  -o models/res10_300x300_ssd_iter_140000.caffemodel

echo "=== Phase 3: Tesseract bundle ==="
scripts/bundle-tesseract-macos.sh

echo "=== Phase 4: ckip NER model (Full only) ==="
if [[ "${INCLUDE_NER}" == "true" ]]; then
  python -c "
from huggingface_hub import snapshot_download
snapshot_download(
    'ckiplab/bert-base-chinese-ner',
    local_dir='ckip_models/bert-base-chinese-ner',
    allow_patterns=['*.json', '*.bin', '*.txt', '*.safetensors', 'tokenizer*'],
)
"
fi

echo "=== Phase 5: Default config ==="
[[ -f config.json ]] || cat > config.json <<'JSON'
{
  "version": 1,
  "custom_terms": {},
  "file_types": [".txt", ".md", ".docx", ".xlsx", ".pptx", ".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tiff"],
  "logo_templates": [],
  "substring_match": true
}
JSON

echo "=== Phase 6: PyInstaller ==="
if [[ -n "${SPEC_FLAG}" ]]; then
  pyinstaller --noconfirm anonymizer.spec -- ${SPEC_FLAG}
else
  pyinstaller --noconfirm anonymizer.spec
fi

APP_PATH="dist/${APP_NAME}.app"
[[ -d "${APP_PATH}" ]] || { echo "PyInstaller did not produce ${APP_PATH}" >&2; exit 2; }

echo "=== Phase 7: codesign ==="
# Sign all inner Mach-O files first, deepest last.
# Find every dylib/so/bundled binary and sign individually with runtime hardening.
while IFS= read -r -d '' target; do
  codesign --force --sign "${APPLE_SIGN_IDENTITY}" \
    --options runtime --timestamp "${target}" >/dev/null 2>&1 || {
      echo "inner sign failed: ${target}" >&2
      exit 3
    }
done < <(find "${APP_PATH}" \( -name "*.dylib" -o -name "*.so" \) -print0)

# Sign the .app bundle itself (--deep walks remaining items)
codesign --force --sign "${APPLE_SIGN_IDENTITY}" \
  --options runtime --timestamp \
  --entitlements entitlements.plist \
  --deep "${APP_PATH}"

echo "=== Phase 8: Verify signature ==="
codesign --verify --deep --strict --verbose=2 "${APP_PATH}"
# spctl will be 'rejected' until stapled — that's expected pre-notarization
spctl -a -vvv -t exec "${APP_PATH}" 2>&1 | head -3 || true

echo "=== Phase 9: zip (ditto) ==="
mkdir -p dist
rm -f "dist/${ZIP_NAME}"
ditto -c -k --keepParent "${APP_PATH}" "dist/${ZIP_NAME}"

if [[ "${SKIP_NOTARIZE:-0}" == "1" ]]; then
  echo "SKIP_NOTARIZE=1 — stopping after codesign."
  echo "Output: dist/${ZIP_NAME} (signed, NOT notarized)"
  exit 0
fi

echo "=== Phase 10: Notarize ==="
xcrun notarytool submit "dist/${ZIP_NAME}" \
  --key "${APPLE_NOTARY_KEY}" \
  --key-id "${APPLE_NOTARY_KEY_ID}" \
  --issuer "${APPLE_NOTARY_ISSUER}" \
  --wait

echo "=== Phase 11: Staple ==="
xcrun stapler staple "${APP_PATH}"
xcrun stapler validate "${APP_PATH}"

echo "=== Phase 12: Re-zip (with stapled ticket) ==="
rm "dist/${ZIP_NAME}"
ditto -c -k --keepParent "${APP_PATH}" "dist/${ZIP_NAME}"

echo ""
echo "✅ Done: dist/${ZIP_NAME}"
du -sh "dist/${ZIP_NAME}"
```

- [ ] **Step 2: Make executable**

```bash
chmod +x build-macos.sh
```

- [ ] **Step 3: Commit**

```bash
git add build-macos.sh
git commit -m "Add macOS build script with codesign + notarize

End-to-end builder: venv -> deps -> assets -> PyInstaller ->
codesign (hardened runtime) -> notarize (App Store Connect API) ->
staple -> ditto zip. SKIP_NOTARIZE=1 for dry runs."
```

---

### Task 2.3: Build the Lite variant locally (skip notarize first)

**Files:**
- No code changes; this task exercises the build.

- [ ] **Step 1: Set minimal env (signing only, skip notarize)**

```bash
export APPLE_SIGN_IDENTITY="Developer ID Application: CHENG-I WU (2798YNATMH)"
export SKIP_NOTARIZE=1
```

- [ ] **Step 2: Run the Lite build**

```bash
./build-macos.sh lite 2>&1 | tee /tmp/build-lite.log
```

Expected: script completes with `Output: dist/DataAnonymizerLite-<ver>-macOS-arm64.zip (signed, NOT notarized)`.

Estimated time: 5–10 minutes (venv creation, pip installs, PyInstaller collect).

- [ ] **Step 3: Sanity check the .app**

```bash
# Structure
ls -la dist/DataAnonymizerLite.app/Contents/
ls dist/DataAnonymizerLite.app/Contents/MacOS/
ls dist/DataAnonymizerLite.app/Contents/Resources/_internal/tesseract-macos/ 2>/dev/null | head -10

# Codesign
codesign --verify --deep --strict --verbose=2 dist/DataAnonymizerLite.app
```
Expected: signature valid, no errors.

- [ ] **Step 4: Run the app**

Open a fresh terminal tab and run:

```bash
/Users/imbad/.claude/anonymizer/dist/DataAnonymizerLite.app/Contents/MacOS/DataAnonymizerLite
```

Expected: browser opens at `http://localhost:<port>` within 5 seconds.

Upload a test file (e.g., a docx) via the Web UI, verify preview + download work. Close the browser tab; app should terminate within 2 minutes.

If the app crashes, check:
```bash
log show --predicate 'process == "DataAnonymizerLite"' --last 5m 2>&1 | tail -30
```

- [ ] **Step 5: Commit nothing (this is a build verification task)**

Record outcome in task tracker. If Phase 1 passed, proceed to Task 2.4.

---

### Task 2.4: Full notarization dry run (Lite)

**Files:**
- No code changes.

- [ ] **Step 1: Set full env**

```bash
export APPLE_SIGN_IDENTITY="Developer ID Application: CHENG-I WU (2798YNATMH)"
export APPLE_NOTARY_KEY="$HOME/.private_keys/AuthKey_WXNK385FUP.p8"
export APPLE_NOTARY_KEY_ID="WXNK385FUP"
export APPLE_NOTARY_ISSUER="237d9fe4-3ec6-47f9-b0c1-36c530d812b5"
unset SKIP_NOTARIZE
```

- [ ] **Step 2: Run full build + notarize**

```bash
./build-macos.sh lite 2>&1 | tee /tmp/build-lite-notarized.log
```

Notarization typically takes 2–15 minutes. If it fails, inspect:
```bash
# Find the submission ID from the log
SUBMISSION_ID=$(grep -oE 'id: [0-9a-f-]+' /tmp/build-lite-notarized.log | head -1 | awk '{print $2}')

xcrun notarytool log "${SUBMISSION_ID}" \
  --key "${APPLE_NOTARY_KEY}" \
  --key-id "${APPLE_NOTARY_KEY_ID}" \
  --issuer "${APPLE_NOTARY_ISSUER}"
```

- [ ] **Step 3: Verify stapled ticket**

```bash
xcrun stapler validate dist/DataAnonymizerLite.app
spctl -a -vvv -t exec dist/DataAnonymizerLite.app
```
Expected:
- `stapler validate: The validate action worked!`
- `spctl ... accepted source=Notarized Developer ID`

- [ ] **Step 4: Verify zip integrity**

```bash
unzip -l "dist/DataAnonymizerLite-$(python3.11 -c 'import re,pathlib;print(re.search(r"__version__\s*=\s*[\x27\x22]([^\x27\x22]+)", pathlib.Path("updater.py").read_text()).group(1))')-macOS-arm64.zip" | tail -5
```
Expected: zip contains `.app` entry with expected size.

- [ ] **Step 5: Smoke test on clean location**

```bash
# Simulate a fresh-download scenario
mkdir -p /tmp/anon-fresh
cp "dist/DataAnonymizerLite-"*"-macOS-arm64.zip" /tmp/anon-fresh/
cd /tmp/anon-fresh
unzip -q DataAnonymizerLite-*.zip

# Add quarantine xattr to simulate "downloaded from the internet"
xattr -w com.apple.quarantine "0083;$(printf '%x' $(date +%s));Safari;" DataAnonymizerLite.app

# Launch from Finder path — should NOT see Gatekeeper warning
open DataAnonymizerLite.app
```
Expected: Browser opens, no "cannot be opened" dialog. Close browser to stop.

- [ ] **Step 6: Record Lite build success**

No git commit for the build run itself. If all checks pass, Lite variant is **shippable**.

---

## Phase 3 — Full Variant

### Task 3.1: Build the Full variant locally

**Files:**
- No code changes; exercises the Full branch of existing scripts.

- [ ] **Step 1: Disk space check**

Run: `df -h /Users/imbad | tail -1`
Required: at least 10 GB free (PyTorch wheels + ckip model + build dir).

- [ ] **Step 2: Full build + notarize**

Environment must still be set from Task 2.4.

```bash
./build-macos.sh full 2>&1 | tee /tmp/build-full-notarized.log
```

Expected: completes with `Output: dist/DataAnonymizer-<ver>-macOS-arm64.zip`.

Estimated time: 15–30 minutes (PyTorch is large; ckip model ~1GB).

- [ ] **Step 3: Verify size budget**

```bash
du -sh dist/DataAnonymizer.app
du -h "dist/DataAnonymizer-"*"-macOS-arm64.zip"
```
Expected: `.app` ≤ 4 GB, zip ≤ 3 GB (spec budget).

If zip > 3 GB, diagnose heaviest subtrees:
```bash
du -sh dist/DataAnonymizer.app/Contents/Resources/* | sort -h | tail -15
```
Most likely culprits: `torch/lib/*.dylib`, `ckip_models/`. Consider adding to `excludes` in `anonymizer.spec` (e.g., `torch.test`, `torch.fx.experimental`), but only after a failing budget.

- [ ] **Step 4: Functional test — NER works**

Launch `dist/DataAnonymizer.app`. In Web UI:

1. Upload a docx or txt containing Chinese names (e.g., `王小明是台大學生`)
2. Preview should highlight `王小明` and `台大` as detected entities
3. Check browser console + app stdout for `transformers` / `ckip` errors

If NER entities don't appear, check:
```bash
log show --predicate 'process == "DataAnonymizer"' --last 5m 2>&1 | grep -E "CKIP|transformers|error" | head -30
```

Most common issue: `HF_HUB_OFFLINE=1` set but model dir missing → runtime_hook didn't find `ckip_models/`. Verify:
```bash
ls dist/DataAnonymizer.app/Contents/Resources/ckip_models/bert-base-chinese-ner/ | head
```

- [ ] **Step 5: Record Full build success**

No git commit.

---

## Phase 4 — CI Automation

### Task 4.1: GitHub Secrets setup (manual, user action)

**Files:**
- No repo changes. User action outside the session.

- [ ] **Step 1: Export signing cert to .p12**

User runs (in a separate terminal — Keychain export is interactive):

```bash
# Open Keychain Access → login keychain → Certificates → find
# "Developer ID Application: CHENG-I WU (2798YNATMH)"
# Right-click → Export → save as ~/Downloads/developer-id.p12
# Set an export password (used next step)
```

Then base64-encode:

```bash
base64 -i ~/Downloads/developer-id.p12 -o ~/Downloads/developer-id.p12.b64
```

- [ ] **Step 2: Base64-encode the .p8**

```bash
base64 -i ~/.private_keys/AuthKey_WXNK385FUP.p8 -o ~/Downloads/notary-key.p8.b64
```

- [ ] **Step 3: Add GitHub Secrets**

Go to https://github.com/Imbad0202/data-anonymizer/settings/secrets/actions and add (Click "New repository secret" for each):

| Name | Value source |
|------|--------------|
| `APPLE_CERT_P12_BASE64` | contents of `~/Downloads/developer-id.p12.b64` |
| `APPLE_CERT_P12_PASSWORD` | password you set during Keychain export |
| `APPLE_SIGN_IDENTITY` | `Developer ID Application: CHENG-I WU (2798YNATMH)` |
| `APPLE_TEAM_ID` | `2798YNATMH` |
| `APPLE_NOTARY_KEY_BASE64` | contents of `~/Downloads/notary-key.p8.b64` |
| `APPLE_NOTARY_KEY_ID` | `WXNK385FUP` |
| `APPLE_NOTARY_ISSUER` | `237d9fe4-3ec6-47f9-b0c1-36c530d812b5` |

- [ ] **Step 4: Delete the base64 files**

```bash
rm ~/Downloads/developer-id.p12 ~/Downloads/developer-id.p12.b64 ~/Downloads/notary-key.p8.b64
```

- [ ] **Step 5: Confirm all 7 secrets show in repo settings**

Browser: the secrets page should list 7 names under Repository secrets.

---

### Task 4.2: Write build-macos.yml

**Files:**
- Create: `.github/workflows/build-macos.yml`

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/build-macos.yml`:

```yaml
name: Build macOS Portable

on:
  push:
    tags:
      - 'v*'

permissions:
  contents: write

jobs:
  build-macos:
    strategy:
      fail-fast: false
      matrix:
        include:
          - name: Full
            variant: full
            artifact: DataAnonymizer
          - name: Lite
            variant: lite
            artifact: DataAnonymizerLite

    runs-on: macos-14   # Apple Silicon runner
    name: Build macOS ${{ matrix.name }}

    env:
      APPLE_SIGN_IDENTITY: ${{ secrets.APPLE_SIGN_IDENTITY }}
      APPLE_TEAM_ID: ${{ secrets.APPLE_TEAM_ID }}
      APPLE_NOTARY_KEY_ID: ${{ secrets.APPLE_NOTARY_KEY_ID }}
      APPLE_NOTARY_ISSUER: ${{ secrets.APPLE_NOTARY_ISSUER }}

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install Homebrew deps
        run: |
          brew install tesseract dylibbundler

      - name: Import signing certificate to temporary Keychain
        env:
          CERT_BASE64: ${{ secrets.APPLE_CERT_P12_BASE64 }}
          CERT_PASSWORD: ${{ secrets.APPLE_CERT_P12_PASSWORD }}
        run: |
          KEYCHAIN_PATH="$RUNNER_TEMP/build.keychain-db"
          KEYCHAIN_PASSWORD="$(openssl rand -base64 20)"

          security create-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"
          security set-keychain-settings -lut 3600 "$KEYCHAIN_PATH"
          security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"

          echo "$CERT_BASE64" | base64 --decode > "$RUNNER_TEMP/cert.p12"
          security import "$RUNNER_TEMP/cert.p12" \
            -k "$KEYCHAIN_PATH" \
            -P "$CERT_PASSWORD" \
            -T /usr/bin/codesign \
            -T /usr/bin/security
          security set-key-partition-list \
            -S apple-tool:,apple:,codesign: \
            -s -k "$KEYCHAIN_PASSWORD" \
            "$KEYCHAIN_PATH"

          # Prepend to default keychain search list
          security list-keychain -d user -s "$KEYCHAIN_PATH" $(security list-keychains -d user | sed s/\"//g)

          rm -f "$RUNNER_TEMP/cert.p12"

      - name: Write notary API key to disk
        env:
          NOTARY_BASE64: ${{ secrets.APPLE_NOTARY_KEY_BASE64 }}
        run: |
          mkdir -p "$RUNNER_TEMP/keys"
          echo "$NOTARY_BASE64" | base64 --decode > "$RUNNER_TEMP/keys/notary.p8"
          chmod 600 "$RUNNER_TEMP/keys/notary.p8"
          echo "APPLE_NOTARY_KEY=$RUNNER_TEMP/keys/notary.p8" >> "$GITHUB_ENV"

      - name: Build ${{ matrix.name }}
        run: |
          ./build-macos.sh ${{ matrix.variant }}

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: ${{ matrix.artifact }}-macos-arm64
          path: dist/*-macOS-arm64.zip

      - name: Cleanup keychain + keys
        if: always()
        run: |
          security delete-keychain "$RUNNER_TEMP/build.keychain-db" || true
          rm -rf "$RUNNER_TEMP/keys"

  # Merge into existing release created by build-windows.yml
  attach-macos-to-release:
    needs: build-macos
    runs-on: ubuntu-latest
    name: Attach macOS zips to release

    steps:
      - name: Download artifacts
        uses: actions/download-artifact@v4
        with:
          path: artifacts
          pattern: '*-macos-arm64'
          merge-multiple: true

      - name: Upload to existing release
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          TAG="${GITHUB_REF#refs/tags/}"
          for zip in artifacts/*.zip; do
            echo "Uploading $zip to release $TAG"
            gh release upload "$TAG" "$zip" --repo "$GITHUB_REPOSITORY" --clobber
          done
```

- [ ] **Step 2: Syntax check**

Run: `cd ~/.claude/anonymizer && python3.11 -c "import yaml; yaml.safe_load(open('.github/workflows/build-macos.yml'))"`
Expected: no output (valid YAML).

Also verify `actionlint` if installed (`brew install actionlint` optional):
```bash
command -v actionlint && actionlint .github/workflows/build-macos.yml || echo "actionlint not installed, skipping"
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/build-macos.yml
git commit -m "Add macOS build workflow (Apple Silicon, codesigned + notarized)

Runs on macos-14 runner. Imports Developer ID cert to a temp
keychain, writes the notary API key to RUNNER_TEMP, invokes
build-macos.sh with both Lite and Full matrix, uploads the
resulting zips to the existing release (created by Windows
workflow) via gh release upload --clobber."
```

---

### Task 4.3: Update release notes template in build-windows.yml

**Files:**
- Modify: `.github/workflows/build-windows.yml`

- [ ] **Step 1: Read current release block**

Check lines in `.github/workflows/build-windows.yml` (around line 196–220 per current state):
- `- name: Create GitHub Release` step
- body under that step

- [ ] **Step 2: Update the release body to include macOS section**

In `.github/workflows/build-windows.yml`, replace the `body: |` block of the release step with:

```yaml
          body: |
            ## 下載

            ### Windows
            | 版本 | 說明 | 適用 |
            |------|------|------|
            | **DataAnonymizerLite-*-Portable.zip** | 免安裝版（推薦），僅自訂詞彙+正則偵測 | 一般使用 |
            | **DataAnonymizer-*-Portable.zip** | 免安裝版，含 NER 人名偵測 | 需要自動偵測人名 |

            ### macOS（Apple Silicon，macOS 12+）
            | 版本 | 說明 | 適用 |
            |------|------|------|
            | **DataAnonymizerLite-*-macOS-arm64.zip** | 免安裝版（推薦） | 一般使用 |
            | **DataAnonymizer-*-macOS-arm64.zip** | 免安裝版，含 NER 人名偵測 | 需要自動偵測人名 |

            已使用 Apple Developer ID 數位簽章並通過公證（notarized），雙擊即可開啟，無 Gatekeeper 警告。

            ## 使用方式

            **Windows**：下載 zip 解壓，雙擊 `.exe` 啟動，瀏覽器會自動開啟。

            **macOS**：下載 zip 解壓，將 `.app` 拖到「應用程式」資料夾（或任意位置），雙擊啟動，瀏覽器會自動開啟。

            共通：將學校設定檔 (`.anonymizer-config.zip`) 放在 `.app` / `.exe` 旁；關閉瀏覽器分頁後程式會自動結束。

            **不需要安裝、不需要管理者權限。**
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/build-windows.yml
git commit -m "Update release notes template to include macOS section"
```

---

### Task 4.4: Trigger CI on a test tag

**Files:**
- No repo changes (publishing action).

- [ ] **Step 1: Bump version**

```bash
# updater.py: find the __version__ line and bump to 2.3.0
python3.11 -c "
import re, pathlib
p = pathlib.Path('updater.py')
s = p.read_text()
s2 = re.sub(r'__version__\s*=\s*[\x27\x22][^\x27\x22]+[\x27\x22]', '__version__ = \"2.3.0\"', s, count=1)
p.write_text(s2)
print(s2.split('\n')[0:3])
"

grep __version__ updater.py | head -1
```

Expected: prints `__version__ = "2.3.0"`.

- [ ] **Step 2: Commit version bump**

```bash
git add updater.py
git commit -m "Bump version to 2.3.0 for macOS release"
```

- [ ] **Step 3: Confirm push with user**

Auto-push rule: `~/.claude/anonymizer/` is NOT in `~/Projects/` → explicit user confirmation required before push.

Ask user: "v2.3.0 commit ready. OK to push to origin + tag?"

If approved:

```bash
git push origin main
git tag v2.3.0
git push origin v2.3.0
```

- [ ] **Step 4: Watch CI**

```bash
gh run watch --repo Imbad0202/data-anonymizer
```

Expected: `build-windows` (2 jobs) + `build-macos` (2 jobs) + `attach-macos-to-release` all green.

- [ ] **Step 5: Verify release assets**

```bash
gh release view v2.3.0 --repo Imbad0202/data-anonymizer | grep asset
```

Expected: 4 assets — 2 Windows zips, 2 macOS zips.

---

## Phase 5 — Documentation

### Task 5.1: macOS first-run guide

**Files:**
- Create: `docs/MACOS_FIRST_RUN.md`

- [ ] **Step 1: Write the guide**

Create `docs/MACOS_FIRST_RUN.md`:

```markdown
# macOS 首次執行說明

## 系統需求

- macOS 12.0（Monterey）以上
- Apple Silicon（M1 / M2 / M3 / M4 系列）

Intel Mac 暫不支援。Apple Silicon 鑑別方式：蘋果選單 → 「關於這台 Mac」→ 晶片顯示 `Apple M*`。

## 下載哪個版本？

| 你的需求 | 建議下載 |
|----------|----------|
| 只需要偵測學校名稱、email、電話、身分證等固定樣式 | **DataAnonymizerLite-*-macOS-arm64.zip** |
| 還需要自動偵測中文人名 | **DataAnonymizer-*-macOS-arm64.zip** |

Lite 版約 250 MB；Full 版約 2 GB（含中文 NER 模型）。兩者功能一致，差別只在「是否偵測人名」。

## 安裝步驟

1. 下載 zip 檔
2. 雙擊 zip 解壓
3. 將 `.app` 拖到「應用程式」資料夾（也可放桌面、隨身碟）
4. 將你拿到的學校設定檔 `.anonymizer-config.zip` 放在 `.app` **旁邊**
5. 雙擊 `.app`
6. 瀏覽器自動開啟操作介面
7. 首次使用會自動提示匯入設定檔
8. 使用完畢 → 關閉瀏覽器分頁，程式會在 2 分鐘內自動結束

不需要安裝、不需要管理者權限。刪除 `.app` 即可移除。

## 常見問題

### 雙擊沒反應 / 出現「無法打開，因為 Apple 無法檢查是否有惡意軟體」

理論上不會出現（本工具已經過 Apple 公證）。如真的出現：

1. 右鍵點 `.app` → 選「打開」
2. 跳出對話框後點「打開」按鈕
3. 之後雙擊就能直接用

### 瀏覽器沒自動打開

手動開瀏覽器到 `http://localhost:8765`（或程式 terminal 顯示的埠號）。

### 圖片 OCR 沒作用

1. 確認使用的圖片格式是 `.jpg` / `.jpeg` / `.png` / `.bmp` / `.tiff`
2. 查看網頁介面的紅色錯誤訊息（若有）
3. 若仍無法解決，回報時請附上「終端機」裡 `.app` 的輸出訊息

### 脫敏結果少了某些詞

1. 開 Web UI → 管理設定 → 新增自訂詞彙
2. 或編輯設定檔 zip 裡的 `custom_terms.json`

### 其他問題

聯繫提供此工具的同事。
```

- [ ] **Step 2: Commit**

```bash
git add docs/MACOS_FIRST_RUN.md
git commit -m "Add macOS first-run user guide (zh-TW)"
```

---

### Task 5.2: Update README.md with macOS download section

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Inspect current README structure**

```bash
grep -n "^#" README.md | head -20
grep -n "下載\|Download\|Windows" README.md | head -10
```

Identify where Windows downloads are documented (or if they aren't, where to add the Downloads section).

- [ ] **Step 2: Add macOS section**

In README.md, find the existing Downloads / 下載 section (Windows). Immediately after it, add:

```markdown
### macOS（Apple Silicon）

需要 macOS 12 以上、M1/M2/M3/M4 系列 Mac。

- [DataAnonymizerLite (macOS) — 免安裝版，推薦](https://github.com/Imbad0202/data-anonymizer/releases/latest)
- [DataAnonymizer (macOS) — 含中文 NER 人名偵測](https://github.com/Imbad0202/data-anonymizer/releases/latest)

首次使用請參考 [macOS 首次執行說明](docs/MACOS_FIRST_RUN.md)。
```

If there is no Downloads section, add one right after the top "## Installation" or equivalent. Do not blindly append at end of file.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Add macOS download section to README"
```

---

## Phase 6 — Wrap-up

### Task 6.1: Confirm release + user smoke test

**Files:**
- None; validation only.

- [ ] **Step 1: Download the macOS Lite zip from the release page**

```bash
gh release download v2.3.0 \
  --repo Imbad0202/data-anonymizer \
  --pattern "DataAnonymizerLite-*-macOS-arm64.zip" \
  --dir /tmp/release-check
```

- [ ] **Step 2: Simulate fresh download + quarantine**

```bash
cd /tmp/release-check
unzip -q DataAnonymizerLite-*.zip
xattr -w com.apple.quarantine "0083;$(printf '%x' $(date +%s));Safari;" DataAnonymizerLite.app
open DataAnonymizerLite.app
```
Expected: browser opens, no Gatekeeper dialog.

- [ ] **Step 3: Run a real-world test**

Upload a real work document (keep local; do not commit). Verify end-to-end pipeline:
- Preview shows detected PII highlighted
- Downloaded result has PII replaced
- File opens without corruption

- [ ] **Step 4: Mark project complete**

Update task tracker. If everything passes, v2.3.0 is the first macOS-supported release. Ready to share the release URL with colleagues.
