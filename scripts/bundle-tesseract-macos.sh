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
# Use Python urllib (system cert bundle) — avoids broken curl caches in
# conda/anaconda environments that override /usr/bin/curl on $PATH.
python3.11 -c "
import ssl, urllib.request
ctx = ssl.create_default_context()
with urllib.request.urlopen('${CHI_TRA_URL}', context=ctx) as r, open('${TESSDATA_DIR}/chi_tra.traineddata', 'wb') as f:
    while True:
        chunk = r.read(1 << 20)
        if not chunk:
            break
        f.write(chunk)
print('Downloaded chi_tra.traineddata')
"

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
