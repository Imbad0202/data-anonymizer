# 資料脫敏工具 Data Anonymizer

[English](README_EN.md)

在將資料傳送給 AI 工具之前，自動偵測並脫敏個人資料（PII）。支援文字檔、Office 文件、PDF 與圖片。

## 功能特色

- **文字脫敏** — 偵測並替換姓名、電話、身分證字號、Email、學校名稱等敏感資訊
- **圖片脫敏** — OCR 文字偵測 + 人臉偵測 + Logo 模板匹配，自動遮蔽敏感區域
- **雙模式** — 假名化（可還原，產生 token 對照表）/ 匿名化（不可逆，符合台灣個資法）
- **多格式支援** — `.txt` `.md` `.docx` `.xlsx` `.pptx` `.pdf` `.jpg` `.png` `.bmp` `.tiff`
- **三層偵測引擎** — 自訂詞彙 → 正則表達式 → NER（ckip-transformers，繁體中文最佳化）
- **GUI 桌面應用** — tkinter 圖形介面，檔案選擇 / 拖放 / 批次處理 / Before/After 預覽
- **Claude Code Hook** — 作為 Claude Code 的 PreToolUse hook，自動攔截並脫敏敏感檔案
- **設定匯出/匯入** — 打包為 `.zip`，一鍵分發給同事
- **Windows 安裝程式** — PyInstaller 打包 + Inno Setup 安裝檔，GitHub Actions 自動建置

## 架構

```
                ┌─────────────────────────────────────────┐
                │           DATA ANONYMIZER v2             │
                ├─────────────────────────────────────────┤
                │  ┌──────────┐   ┌──────────────────┐   │
                │  │   GUI    │   │  CLI / Hook Mode  │   │
                │  │(tkinter) │   │ (Claude Code)     │   │
                │  └────┬─────┘   └──────┬───────────┘   │
                │       └───────┬────────┘               │
                │               ▼                        │
                │  ┌──────────────────────────┐          │
                │  │      Core Engine          │          │
                │  │  Text: custom→regex→NER   │          │
                │  │  Image: OCR→Face→Logo     │          │
                │  │  Mode: reversible / irreversible │   │
                │  └──────────────────────────┘          │
                └─────────────────────────────────────────┘
```

## 快速開始

### 作為 Claude Code Hook 使用

```bash
# 1. 安裝
cd ~/.claude/anonymizer
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. 執行設定精靈
.venv/bin/python setup.py

# 3. Hook 會自動攔截 Claude Code 對敏感路徑的讀取操作
```

### 作為 GUI 桌面應用使用

```bash
# 開發模式啟動
.venv/bin/python gui/app.py
```

或下載 [GitHub Releases](https://github.com/Imbad0202/data-anonymizer/releases) 的 Windows 安裝程式。

### 作為 Python 模組使用

```python
from anonymizer import Anonymizer

config = {
    "custom_terms": {"schools": ["國立台灣大學", "國立清華大學"]},
    "substring_match": True,
}

# 假名化（可還原）
anon = Anonymizer(config=config, session_id="demo", use_ner=False, reversible=True)
result, summary = anon.anonymize_text("張三就讀國立台灣大學，電話 0912345678")
print(result)   # __ANON:PERSON_001__ 就讀 __ANON:SCHOOL_001__，電話 __ANON:PHONE_001__

# 匿名化（不可逆）
anon = Anonymizer(config=config, session_id="demo", use_ner=False, reversible=False)
result, summary = anon.anonymize_text("張三就讀國立台灣大學，電話 0912345678")
print(result)   # [PERSON] 就讀 [SCHOOL]，電話 [PHONE]
```

## 圖片脫敏

三階段管線處理：

1. **OCR 文字 PII** — Tesseract OCR 提取文字 → 現有偵測引擎辨識敏感資訊 → 定位像素座標
2. **人臉偵測** — OpenCV DNN（res10_300x300_ssd_iter_140000.caffemodel），CPU-only
3. **Logo 偵測** — OpenCV matchTemplate 多尺度搜尋（0.5x–2.0x）

```python
from image_anonymizer import ImageAnonymizer

config = {"custom_terms": {"schools": ["國立台灣大學"]}}
img_anon = ImageAnonymizer(config=config, use_ner=False)
output_path, summary = img_anon.anonymize_image("input.jpg", output_dir="output/")
```

## 批次處理

```python
from batch import run_batch

result = run_batch(
    input_dir="./sensitive_docs",
    output_dir=None,  # 預設：sensitive_docs_anonymized/
    config=config,
    reversible=False,
    use_ner=False,
)
print(result.summary())
```

## 設定檔

`config.json` 結構（schema v1）：

```json
{
    "version": 1,
    "custom_terms": {
        "schools": ["國立台灣大學", "國立清華大學"],
        "people": ["張三", "李四"]
    },
    "file_types": [".txt", ".md", ".docx", ".pdf", ".jpg", ".png"],
    "logo_templates": ["ntu_logo.png"],
    "substring_match": true
}
```

設定可匯出為 `.anonymizer-config.zip`（含 logo 模板），分發給同事一鍵匯入。

## 建置 Windows 安裝程式

推送版本 tag 即可觸發 GitHub Actions 自動建置：

```bash
git tag v2.0.0
git push origin v2.0.0
```

產出兩個版本：
- **Full** — 含 NER（PyTorch + ckip-transformers），約 2-3GB
- **Lite** — 僅自訂詞彙 + 正則表達式，約 150-250MB

## 測試

```bash
.venv/bin/python -m pytest -v
```

目前 168 個測試全數通過。

## 專案結構

```
anonymizer.py          # 核心文字脫敏引擎
image_anonymizer.py    # 圖片脫敏管線（OCR + Face + Logo）
hook_router.py         # Claude Code PreToolUse hook 路由
batch.py               # 批次處理
config_manager.py      # 設定匯出/匯入
updater.py             # 自動更新檢查
mapping_manager.py     # Token 對照表管理
restore.py             # PostToolUse 還原 hook
detectors/             # 偵測引擎（custom, regex, NER）
parsers/               # 檔案解析器（text, docx, xlsx, pptx, pdf, image）
gui/                   # tkinter GUI
  app.py               # 主視窗
  preview.py           # Before/After 預覽面板
tests/                 # 測試（168 tests）
anonymizer.spec        # PyInstaller 打包規格
installer.iss          # Inno Setup 安裝程式腳本
.github/workflows/     # CI/CD
```

## 授權

Private repository.
