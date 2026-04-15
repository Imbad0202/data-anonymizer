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
