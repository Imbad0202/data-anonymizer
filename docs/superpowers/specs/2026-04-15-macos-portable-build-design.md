# macOS Portable Build — Design Spec

**Date:** 2026-04-15
**Status:** Draft (awaiting user review)
**Target release:** v2.3.0 (macOS support)

## Context

Data Anonymizer v2.2.1 目前僅發布 Windows Portable zip（Full + Lite 兩種變體）。`.github/workflows/build-windows.yml` 自動化 Windows 建置。macOS 使用者無法直接使用 release 資產；本機 dev 模式可跑，但同事分發場景缺解法。

本 spec 設計 macOS 對應的分發管道：架構、簽章策略、自動化路線、驗收條件。

## Goals

1. 讓 macOS 使用者（主要對象：校內同事）**雙擊即可啟動**的 Portable zip
2. 維持與 Windows release 對稱（Full / Lite 雙變體）
3. 使用者不需看到 Gatekeeper 警告（走正式 codesign + notarize）
4. 最終自動化（GitHub Actions），但先本機驗證再寫 CI
5. OCR（圖片脫敏）功能在 Mac 上也可用，使用者不用另外裝 Tesseract

## Non-Goals

- Intel Mac（x86_64）支援 — 僅 arm64（Apple Silicon），2020 年後的 Mac
- Universal2 binary — 技術坑多、包體雙倍，非必要
- App Store 分發 — 走 Developer ID 外部分發，不走 App Store
- dmg / pkg installer — 跟 Windows 對稱採 Portable zip，未來再升級
- ckip-transformers 的 GPL-3.0 評估 — 繼承既有對外策略（已於 ISMS 確認書記錄注意事項）

## Design Decisions（已經與用戶確認）

| 決策 | 選擇 | 理由 |
|------|------|------|
| 分發型態 | Portable zip | 與 Windows 對稱、最低使用者門檻 |
| 建置路線 | 先本機驗證 → 再寫 CI | 先解 macOS 專屬坑再自動化 |
| 變體 | Full + Lite 雙變體 | 與 Windows 對稱 |
| 架構 | arm64 only | 校內同事 2020+ Mac 皆為 arm64 |
| Tesseract OCR | Bundle 進 zip（對稱 Windows） | 使用者真正「解壓即用」 |
| 簽章 | 正式 codesign + notarize | 用戶已有 Apple Developer 帳號 |
| Entitlements | 最嚴格（JIT 必要項） | notarize 越窄越順 |

## 用戶前置資產（已備齊）

| 項目 | 值 |
|------|----|
| Apple ID | `crucify22@hotmail.com` |
| Team ID | `2798YNATMH` |
| Developer ID Application 憑證 | `Developer ID Application: CHENG-I WU (2798YNATMH)`（SHA: `972B1431D84402689EB7DE779EDC4D1C717CD7BC`） |
| API Key ID | `WXNK385FUP` |
| API Key Issuer | `237d9fe4-3ec6-47f9-b0c1-36c530d812b5` |
| API Key `.p8` 本機位置 | `~/.private_keys/AuthKey_WXNK385FUP.p8`（權限 600） |
| notarytool 連線驗證 | ✅ 通過 |

**機敏性：** `.p8` 與 Team ID 不進 git。CI 走 GitHub Secrets（見下方 CI 章節）。

## Architecture

### 檔案結構

```
~/.claude/anonymizer/
├── anonymizer.spec                    # 擴充：新增 macOS entitlements + icon 支援
├── build-macos.sh                     # 新增：本機建置腳本
├── entitlements.plist                 # 新增：notarize 用 entitlements
├── assets/
│   ├── icon.ico                       # 既有（Windows）
│   └── icon.icns                      # 新增（macOS app icon）
├── .github/workflows/
│   ├── build-windows.yml              # 既有
│   └── build-macos.yml                # 新增（Phase 2）
└── docs/
    └── MACOS_FIRST_RUN.md             # 新增：Mac 使用者首次執行說明（中文）
```

### 建置流程（本機）

```
build-macos.sh (lite | full)
  │
  ├─ 1. Setup venv（arm64 python 3.11）
  ├─ 2. pip install deps（lite/full 分支）
  ├─ 3. Download 模型資源
  │     ├─ OpenCV face model (deploy.prototxt + res10 caffemodel)
  │     ├─ [full only] ckip NER model（huggingface snapshot_download）
  │     └─ Tesseract bundle（macOS arm64 from Homebrew bottle）
  ├─ 4. pyinstaller anonymizer.spec [-- --lite]
  │     └─ 產出 dist/DataAnonymizer[Lite].app (onedir bundle)
  ├─ 5. codesign（hardened runtime + entitlements.plist）
  │     └─ 對所有 .dylib / .so / 子 binary 遞迴簽
  ├─ 6. zip (ditto, 保留符號連結與權限)
  │     └─ dist/DataAnonymizer[Lite]-<ver>-macOS-arm64.zip
  ├─ 7. xcrun notarytool submit --wait
  └─ 8. xcrun stapler staple（把 notarization ticket 釘進 .app）
        └─ 重新 zip，覆蓋 Step 6 的 zip
```

### anonymizer.spec 擴充

現有 spec 已支援 macOS 到一定程度（`target_arch=None`、`codesign_identity=None`），需要以下調整：

1. **Platform-aware datas**：Tesseract bundle 路徑在 macOS 上是 `_internal/tesseract-macos/`（避免與 Windows 的 `_internal/tesseract/` 撞）
2. **icon 平台分支**：`.ico`（Windows）vs `.icns`（macOS），以 `sys.platform` 判斷
3. **BUNDLE block 新增**：macOS 需要 `BUNDLE()` 才能產出 `.app`，包含：
   - `bundle_identifier = 'tw.org.heeact.dataanonymizer'`
   - `info_plist` dict：包含 `LSUIElement=False`、`NSHighResolutionCapable=True`、`CFBundleShortVersionString` 從 `updater.__version__` 讀
4. **console=False、windowed=True**：macOS 雙擊 `.app` 不應跳 terminal

### entitlements.plist

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

**理由：** Python bytecode cache + PyTorch（Full 版）會 trigger executable memory checks；JIT 是 PyInstaller bootloader 需要。其他 entitlement 先不開，build 後驗證若有 crash 再疊。

### build-macos.sh 骨架

```bash
#!/usr/bin/env bash
set -euo pipefail

# build-macos.sh [lite|full]
VARIANT="${1:-lite}"
VERSION="$(python3 -c 'import updater; print(updater.__version__)')"

case "$VARIANT" in
  lite) APP_NAME="DataAnonymizerLite"; SPEC_ARGS="-- --lite" ;;
  full) APP_NAME="DataAnonymizer"; SPEC_ARGS="" ;;
  *) echo "Usage: $0 [lite|full]"; exit 1 ;;
esac

ZIP_NAME="${APP_NAME}-${VERSION}-macOS-arm64.zip"

# 環境變數檢查（簽章 / 公證必要）
: "${APPLE_TEAM_ID:?need APPLE_TEAM_ID}"
: "${APPLE_SIGN_IDENTITY:?need APPLE_SIGN_IDENTITY}"  # e.g. "Developer ID Application: CHENG-I WU (2798YNATMH)"
: "${APPLE_NOTARY_KEY:?need APPLE_NOTARY_KEY}"        # path to .p8
: "${APPLE_NOTARY_KEY_ID:?need APPLE_NOTARY_KEY_ID}"
: "${APPLE_NOTARY_ISSUER:?need APPLE_NOTARY_ISSUER}"

# 1. Clean + venv
rm -rf dist build .venv-build
python3.11 -m venv .venv-build
source .venv-build/bin/activate
pip install --upgrade pip pyinstaller
pip install -r requirements.txt
[ "$VARIANT" = "lite" ] && pip uninstall -y torch transformers ckip-transformers

# 2. Assets（face model + tesseract + ckip model）
#    詳細 download 步驟見「資源備齊」章節

# 3. PyInstaller
pyinstaller --noconfirm anonymizer.spec $SPEC_ARGS

# 4. Codesign（遞迴簽 bundle 內所有 binary）
find "dist/${APP_NAME}.app" -name '*.dylib' -o -name '*.so' | while read -r f; do
  codesign --force --sign "$APPLE_SIGN_IDENTITY" --options runtime --timestamp "$f"
done
codesign --force --sign "$APPLE_SIGN_IDENTITY" --options runtime --timestamp \
  --entitlements entitlements.plist --deep "dist/${APP_NAME}.app"

# 5. Verify signature
codesign --verify --deep --strict --verbose=2 "dist/${APP_NAME}.app"
spctl -a -vvv -t exec "dist/${APP_NAME}.app" || true   # 預期「rejected」（還沒 staple）

# 6. Zip (用 ditto，保留 xattr / symlink / 權限)
ditto -c -k --keepParent "dist/${APP_NAME}.app" "dist/${ZIP_NAME}"

# 7. Notarize
xcrun notarytool submit "dist/${ZIP_NAME}" \
  --key "$APPLE_NOTARY_KEY" \
  --key-id "$APPLE_NOTARY_KEY_ID" \
  --issuer "$APPLE_NOTARY_ISSUER" \
  --wait

# 8. Staple（把 ticket 釘進 .app，使用者之後離線也能驗）
xcrun stapler staple "dist/${APP_NAME}.app"
xcrun stapler validate "dist/${APP_NAME}.app"

# 9. Re-zip（stapled 版本）
rm "dist/${ZIP_NAME}"
ditto -c -k --keepParent "dist/${APP_NAME}.app" "dist/${ZIP_NAME}"

echo "✅ Done: dist/${ZIP_NAME}"
```

### 資源備齊

| 資源 | 來源 | 目的地 |
|------|------|--------|
| OpenCV face model | `raw.githubusercontent.com/opencv/...`（同 Windows） | `models/deploy.prototxt`, `models/res10_...caffemodel` |
| Tesseract binary + libs | `brew fetch --bottle-tag=arm64_sonoma tesseract` → 解壓 | `_internal/tesseract-macos/` |
| Tesseract tessdata | `tesseract` bottle 內附 `eng.traineddata`；`chi_tra.traineddata` 從 `tessdata_best` github raw 下載 | `_internal/tesseract-macos/tessdata/` |
| ckip NER model（Full only） | `huggingface_hub.snapshot_download('ckiplab/bert-base-chinese-ner')` | `ckip_models/bert-base-chinese-ner/` |

**Tesseract dylib rpath 處理：** Homebrew bottle 的 `tesseract` 依賴 `libtesseract`、`leptonica` 等 dylib，其 `install_name` 指向 `/opt/homebrew/opt/...`。Bundle 進 app 後這些路徑不存在。解法：

```bash
# 把依賴 dylib copy 進 _internal/tesseract-macos/lib/
# 用 install_name_tool 改寫 rpath：
install_name_tool -change /opt/homebrew/opt/leptonica/lib/liblept.5.dylib \
  @executable_path/../lib/liblept.5.dylib _internal/tesseract-macos/tesseract
```

細節在 `build-macos.sh` 的「Tesseract bundle」區塊處理，使用 `otool -L` + `install_name_tool -change` 迴圈，非 PyInstaller 職責。

### web_app.py 啟動路徑調整

現有 `gui/web_app.py` 在 Windows 下會找 `_internal/tesseract/tesseract.exe`。macOS 下需找 `_internal/tesseract-macos/tesseract`。建議改為：

```python
# gui/web_app.py 或 parsers/image_parser.py
import sys, os
if sys.platform == 'darwin':
    TESSERACT_SUBDIR = 'tesseract-macos'
    TESSERACT_BIN = 'tesseract'
else:
    TESSERACT_SUBDIR = 'tesseract'
    TESSERACT_BIN = 'tesseract.exe'
```

搜尋 code base 中所有 hardcoded `tesseract.exe` / `_internal/tesseract/`，集中到一個 helper（例如 `parsers/tesseract_path.py`）。這部分改動納入 implementation plan，非本 spec 要解的範圍。

## Info.plist 內容

```python
# anonymizer.spec 的 BUNDLE block
BUNDLE(
    coll,
    name=f'{app_name}.app',
    icon=os.path.join(BASE_DIR, 'assets', 'icon.icns'),
    bundle_identifier='tw.org.heeact.dataanonymizer' + ('.lite' if lite_mode else ''),
    info_plist={
        'CFBundleShortVersionString': VERSION,
        'CFBundleVersion': VERSION,
        'NSHumanReadableCopyright': '© 2026 CHENG-I WU. CC BY-NC 4.0.',
        'NSHighResolutionCapable': True,
        'LSUIElement': False,
        'LSMinimumSystemVersion': '12.0',
        'NSRequiresAquaSystemAppearance': False,
    },
)
```

**Bundle identifier** 用 `tw.org.heeact.dataanonymizer`（HEEACT 是用戶雇主，合適 reverse DNS 前綴）；Lite 版加 `.lite` suffix 避免與 Full 版衝突。

## CI 自動化（Phase 2，本機驗證後執行）

`.github/workflows/build-macos.yml` 新增：

### GitHub Secrets 需要
| Secret | 值 |
|--------|----|
| `APPLE_SIGN_IDENTITY` | `Developer ID Application: CHENG-I WU (2798YNATMH)` |
| `APPLE_CERT_P12` | 從 Keychain 匯出的 `.p12` 檔 base64（內含憑證 + 私鑰） |
| `APPLE_CERT_P12_PASSWORD` | `.p12` 匯出密碼 |
| `APPLE_TEAM_ID` | `2798YNATMH` |
| `APPLE_NOTARY_KEY_BASE64` | `~/.private_keys/AuthKey_WXNK385FUP.p8` base64 |
| `APPLE_NOTARY_KEY_ID` | `WXNK385FUP` |
| `APPLE_NOTARY_ISSUER` | `237d9fe4-3ec6-47f9-b0c1-36c530d812b5` |

### Runner 策略

- `runs-on: macos-14`（arm64 runner）
- Matrix：`{lite: [true, false]}`，與 Windows 對稱
- Keychain 建立 tmp keychain → 匯入 `.p12` → build-macos.sh → 毀掉 keychain
- Release job 跟 Windows 共用 `release` job（改成 `needs: [build-windows, build-macos]`）

### release notes 調整

既有 `build-windows.yml` 的 release notes body 要擴充新增 macOS 下載說明（含首次開啟步驟——即使 notarized 仍要跟使用者講清楚）。

## 使用者文件

新增 `docs/MACOS_FIRST_RUN.md`：

- 下載哪個 zip（Lite vs Full 判斷樹）
- 解壓 → 拖 `.app` 到 `/Applications`（或任意位置）
- 雙擊 → 瀏覽器自動開
- 若 macOS 版本過低：提示系統需求 (macOS 12.0+)
- Troubleshooting：Gatekeeper 擋（若 notarization 某次失敗）、埠口衝突、OCR 沒作用

README.md 也要新增 macOS 下載區塊，與 Windows 並列。

## Phase 0 — 本機預先驗證（先於 implementation plan 執行）

用戶這邊可用的驗證環境檢查：

```bash
# 1. Xcode Command Line Tools
xcode-select -p
# 預期：/Library/Developer/CommandLineTools 或 /Applications/Xcode.app/...

# 2. Homebrew
which brew

# 3. Python 3.11 arm64
python3.11 -c "import sys, platform; print(sys.version, platform.machine())"
# 預期：3.11.x ... arm64

# 4. Tesseract bottle 可下載
brew fetch --bottle-tag=arm64_sonoma tesseract --force
```

這些在 implementation plan 第一步執行，任何一項失敗就 blocker。

## 驗收條件（Acceptance Criteria）

### Lite 版（優先）
- [ ] `dist/DataAnonymizerLite-<ver>-macOS-arm64.zip` 產出
- [ ] `codesign --verify --deep --strict` 通過
- [ ] `xcrun notarytool submit` 回傳 `status: Accepted`
- [ ] `xcrun stapler validate` 通過
- [ ] zip 解壓後 `spctl -a -vvv -t exec` 顯示 `accepted source=Notarized Developer ID`
- [ ] 雙擊 `.app` 瀏覽器會自動開 `http://localhost:<port>`
- [ ] Web UI 上傳 docx/pdf 脫敏流程走通
- [ ] 圖片 OCR：上傳 jpg/png 能偵測並打碼（Tesseract bundle 生效）
- [ ] zip 大小 < 400MB（Lite 目標）

### Full 版
- [ ] `dist/DataAnonymizer-<ver>-macOS-arm64.zip` 產出
- [ ] Lite 版上述所有項目 + NER 功能（人名偵測）可用
- [ ] zip 大小 < 3GB（Full 目標，PyTorch 是大頭）

### CI 自動化（Phase 2）
- [ ] Push tag `v2.3.0` 觸發 `build-macos.yml`
- [ ] macOS job 產出 2 個 zip，Windows job 繼續產 2 個 zip
- [ ] release 單一 release 同時掛 4 個 assets
- [ ] release notes 包含 macOS 使用說明

## 風險與緩解

| 風險 | 機率 | 衝擊 | 緩解 |
|------|------|------|------|
| Tesseract dylib rpath 調整失敗 | 中 | 高（OCR 壞掉） | Phase 0 先手動跑一次 `install_name_tool`，驗證 `otool -L` 輸出 |
| PyTorch Full 版打包過大 / 超時 | 中 | 中 | Lite 先過，Full 用 `--exclude-module` 砍掉不必要的 torch subpackages |
| notarization 被拒 | 低 | 高 | entitlements 最小化 + hardened runtime；有拒絕訊息再針對性開豁免 |
| GitHub macos-14 runner 排隊 | 低 | 低 | CI job 跑時間拉長，可接受 |
| `.p12` 匯出 / CI Keychain 設定錯誤 | 中 | 高（CI 不能簽） | Phase 2 前先手動跑一次「tmp keychain + 匯入 + codesign」流程驗證 |
| OCR chi_tra.traineddata 下載失敗 | 低 | 中 | 同 Windows workflow，使用 `tessdata_best` 的 github raw，可 fallback `tessdata_fast` |
| Homebrew bottle URL 會漂移 | 低 | 中 | 用 `brew fetch --bottle-tag` 抓當下版本，不硬寫 URL |

## 分階段執行策略

| Phase | 目標 | 驗收 |
|-------|------|------|
| 0 | 環境檢查 + Tesseract rpath 手動驗證 | Phase 0 checklist 全綠 |
| 1 | Lite 版本機建置 → 簽章 → 公證 → 雙擊能開 | Lite 驗收條件全綠 |
| 2 | Full 版本機建置（同流程） | Full 驗收條件全綠 |
| 3 | 寫 `build-macos.yml`，首次 push tag 觸發 | CI 驗收條件全綠 |
| 4 | 更新 README、`docs/MACOS_FIRST_RUN.md`、release notes 模板 | 文件 PR 合入 |

各 Phase 獨立可 ship，Phase 1 通過就算「mac 使用者有東西可用」。

**PR 切分：** Phase 0 + Phase 1（Lite build 流程）為 PR #A，Phase 2（Full）為 PR #B，Phase 3（CI）為 PR #C，Phase 4（文件）為 PR #D。每 PR 可獨立合入、獨立回滾。

## 開放問題（Open Questions）

無。所有設計決策已由用戶拍板。

## 參考

- Apple: [Notarizing macOS software before distribution](https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution)
- Apple: [Hardened Runtime](https://developer.apple.com/documentation/security/hardened_runtime)
- PyInstaller: [macOS Bundle](https://pyinstaller.org/en/stable/spec-files.html#spec-file-options-for-a-macos-bundle)
- Homebrew: [brew fetch --bottle-tag](https://docs.brew.sh/Manpage)
