# 範例二：批次處理 Office 檔案

## 使用者需求

> 我有一整個資料夾的 Word、Excel、PDF 文件需要批次脫敏，產出新的脫敏版本到另一個資料夾。

## 基本批次處理

```python
from batch import run_batch

config = {
    "custom_terms": {
        "schools": ["國立成功大學", "成大"],
        "people": ["王教授", "李主任"],
        "departments": ["電機工程學系", "企業管理學系"],
    },
    "file_types": [".docx", ".xlsx", ".pptx", ".pdf", ".txt", ".md"],
    "substring_match": True,
}

result = run_batch(
    input_dir="./school_reports",
    output_dir=None,           # None = 自動產出至 ./school_reports_anonymized/
    config=config,
    reversible=False,          # 不可逆模式（適合對外分享）
    use_ner=False,             # 不啟用 NER（速度較快）
)

print(result.summary())
```

### 輸出

```
批次處理完成：共 42 個檔案、已處理 42 個、發現個資 28 個
```

輸出資料夾結構會保留原始目錄階層：

```
school_reports_anonymized/
  ├── 109_self_evaluation.docx      # 已脫敏
  ├── budget/
  │   ├── 110_budget.xlsx           # 已脫敏
  │   └── summary.pdf               # 已脫敏
  └── meeting_notes/
      └── 2024-01-15.docx           # 已脫敏
```

## 含圖片的批次處理

批次處理同時支援圖片檔案，自動走圖片脫敏管線（OCR + 人臉偵測 + Logo 偵測）。

```python
config["file_types"] = [".docx", ".xlsx", ".pdf", ".jpg", ".png"]
config["logo_templates"] = ["school_logo.png"]  # Logo 模板用於模板匹配

result = run_batch(
    input_dir="./school_reports",
    output_dir="./cleaned_output",
    config=config,
    reversible=False,
    use_ner=False,
)
```

圖片中的敏感內容會以黑色方塊遮蔽：
- **OCR 偵測到的文字 PII**（人名、電話等）
- **人臉**（OpenCV DNN 人臉偵測）
- **學校 Logo**（多尺度模板匹配）

## 帶進度回呼的批次處理

處理大量檔案時，可傳入 `progress_callback` 追蹤進度：

```python
def on_progress(current, total, filename):
    percent = (current / total) * 100
    print(f"[{percent:.0f}%] 處理中：{filename}")

result = run_batch(
    input_dir="./school_reports",
    output_dir=None,
    config=config,
    reversible=True,          # 假名化模式（保留還原能力）
    use_ner=False,
    progress_callback=on_progress,
)
```

### 輸出

```
[2%] 處理中：109_self_evaluation.docx
[5%] 處理中：110_budget.xlsx
[7%] 處理中：meeting_notes/2024-01-15.docx
...
[100%] 處理中：附件_09.pdf
批次處理完成：共 42 個檔案、已處理 42 個、發現個資 28 個
```

## 檢查個別檔案結果

`BatchResult.file_results` 記錄每個檔案的處理狀態：

```python
for fr in result.file_results:
    status_icon = {"ok": "v", "skipped": "-", "error": "x"}[fr["status"]]
    print(f"[{status_icon}] {fr['file']}: {fr['detail']}")
```

### 輸出

```
[v] 109_self_evaluation.docx: 已脫敏檔案《109_self_evaluation.docx》：PERSON 5 個、PHONE 2 個、SCHOOL 3 個
[v] budget/110_budget.xlsx: 已脫敏檔案《110_budget.xlsx》：PERSON 3 個
[-] README.md: 不支援的檔案格式
[v] meeting_notes/2024-01-15.docx: 已脫敏檔案《2024-01-15.docx》：EMAIL 1 個、PERSON 8 個
```

## Web UI 批次處理

也可透過 Web UI 進行批次處理，無需撰寫程式碼：

```bash
# 啟動 Web UI
.venv/bin/python gui/web_app.py

# 瀏覽器自動開啟，拖放檔案即可處理
# 處理完成後可一鍵下載所有脫敏結果（ZIP）
```

Web UI 提供：
- 拖放上傳多個檔案
- Before / After 並排預覽
- SSE 即時進度條
- 一鍵下載全部結果
- 設定匯入 / 匯出
