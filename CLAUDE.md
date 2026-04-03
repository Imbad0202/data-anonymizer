# CLAUDE.md

## Project Overview

Data Anonymizer — 本地端個資偵測與脫敏工具（PII detection & anonymization）。在將資料傳送給 AI 工具前，自動偵測並脫敏個人資料。支援文字檔、Office 文件、PDF 與圖片。

主要使用情境：
- **Claude Code Hook**：作為 PreToolUse hook，自動攔截並脫敏 Claude Code 讀取的敏感檔案
- **Web UI**：Flask + HTML/CSS/JS 本地 Web 介面，拖放上傳、Before/After 預覽
- **Python API**：`from anonymizer import Anonymizer` 直接呼叫
- **批次處理**：整個資料夾遞迴脫敏

## Architecture

### 三層偵測引擎（Detection Pipeline）

優先順序：Custom Terms → Regex → NER（ckip-transformers）

| 層級 | 檔案 | 偵測對象 |
|------|------|---------|
| Custom | `detectors/custom.py` | 自訂學校、人名、學院等（substring match） |
| Regex | `detectors/regex_detector.py` | Email、電話、身分證字號、URL |
| NER | `detectors/ner.py` | ckip-transformers 繁中 NER（PERSON、ORG 等） |

偵測結果以 `Span` 物件表示（`models.py`），重疊時由 `resolve_spans()` 按長度優先、來源優先排序。

### 雙模式（Dual Mode）

- **假名化（Reversible）**：`__ANON:CATEGORY_001__` token，可透過 mapping 還原
- **匿名化（Irreversible）**：`[CATEGORY]` 標記，不可逆，符合台灣個資法

### 檔案解析器（Parsers）

位於 `parsers/`：text、docx、xlsx、pptx、pdf、image（PIL + Tesseract OCR）。

### Hook 整合

- `hook_router.py`：PreToolUse hook 入口，攔截 Read/Edit/Grep/Bash
- `restore.py`：PostToolUse hook，還原 Write/Edit 中的 `__ANON:...__` token

## Key Files

```
anonymizer.py          # 核心引擎：Anonymizer class + anonymize_text/file
image_anonymizer.py    # 圖片脫敏（OCR + Face + Logo detection）
hook_router.py         # Claude Code PreToolUse hook 路由
restore.py             # Claude Code PostToolUse 還原 hook
batch.py               # 批次資料夾處理
models.py              # Span model + overlap resolver
mapping_manager.py     # Token 對照表（reversible mode）
config_manager.py      # 設定匯出/匯入（.zip）
setup.py               # 互動式設定精靈
updater.py             # GitHub Releases 自動更新檢查
learned_terms_manager.py # 不確定詞彙學習管理
detectors/             # 三層偵測引擎
parsers/               # 檔案格式解析器
gui/web_app.py         # Flask Web UI 後端
gui/static/            # CSS + JS
gui/templates/         # HTML 模板
tests/                 # 168+ tests
```

## Development Commands

```bash
# 安裝依賴
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 執行全部測試
.venv/bin/python -m pytest -v

# 執行特定測試
.venv/bin/python -m pytest tests/test_anonymizer.py -v
.venv/bin/python -m pytest tests/test_hook_router.py -v
.venv/bin/python -m pytest tests/test_e2e.py -v

# 啟動 Web UI（開發模式）
.venv/bin/python gui/web_app.py

# 執行設定精靈
.venv/bin/python setup.py

# 清除過期暫存檔
.venv/bin/python anonymizer.py --cleanup
```

## Design System

所有 UI 視覺決策定義於 `DESIGN.md`。修改 Web UI 前必須先閱讀。
- 主色：Teal (`#0F766E`)
- 字型：DM Sans + Noto Sans TC + Geist Mono
- 三欄佈局：左側偵測摘要 | 中間原始內容 | 右側脫敏結果

## Coding Conventions

- 敏感資料檔案（`config.json`、`learned_terms.json`、`mappings/`）已加入 `.gitignore`，禁止提交
- Hook 內部路徑保護：只保護設定與 mapping 檔，原始碼 `.py` 不保護（開發需要）
- 測試中 `use_ner=False` 避免載入大型模型，加速測試
- Windows 跨平台相容：注意 `fcntl`（Unix only）、temp 路徑、`chmod` 差異
- 版本號定義於 `updater.py` 的 `__version__`，CI 建置時同步

## CI/CD

- `.github/workflows/build-windows.yml`：推送版本 tag（`v*`）觸發 Windows 安裝程式建置
- 產出 Full（含 NER，~2-3GB）和 Lite（僅 custom + regex，~150-250MB）兩版本
- PyInstaller 打包規格：`anonymizer.spec`
- Inno Setup 安裝程式：`installer.iss`（Full）、`installer-lite.iss`（Lite）

## License

CC BY-NC 4.0
