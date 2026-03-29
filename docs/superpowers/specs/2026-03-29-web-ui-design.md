# Web UI — 取代 tkinter GUI

## Summary

用 Flask + 純 HTML/CSS/JS 取代現有的 tkinter GUI（`gui/app.py`, `gui/preview.py`）。
使用者雙擊 exe 後自動開啟瀏覽器，操作完全在 `localhost` Web 介面完成。
視覺設計遵循 `DESIGN.md`（teal 主色、亮色主題、色彩編碼 PII 類別、三欄佈局）。

## Motivation

- tkinter 在 Windows 上外觀老舊，無法做出接近 SaaS 工具的體驗
- Web UI 天然支援拖放、即時預覽、響應式佈局
- Flask 打包到 PyInstaller 是成熟做法，不增加分發複雜度
- 同事只要雙擊 exe，瀏覽器自動開，不需要知道 localhost 是什麼

## Architecture

```
┌─────────────────────────────────────────────┐
│               PyInstaller exe               │
│  ┌────────────────────────────────────────┐ │
│  │         Flask Server (localhost)       │ │
│  │  ┌──────────┐  ┌───────────────────┐  │ │
│  │  │  Routes   │  │  Static Files     │  │ │
│  │  │  /api/*   │  │  HTML/CSS/JS      │  │ │
│  │  └─────┬────┘  └───────────────────┘  │ │
│  │        │                               │ │
│  │        ▼                               │ │
│  │  ┌──────────────────────────────┐     │ │
│  │  │     Core Engine (existing)    │     │ │
│  │  │  Anonymizer / ImageAnonymizer │     │ │
│  │  │  Parsers / Detectors / etc.   │     │ │
│  │  └──────────────────────────────┘     │ │
│  └────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
         │
         ▼ webbrowser.open()
    ┌──────────┐
    │  Browser  │  ← 使用者看到的介面
    └──────────┘
```

## Technology Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Backend framework | Flask | 輕量、成熟、PyInstaller 友善 |
| Frontend | 純 HTML/CSS/JS | 零 build step，直接 static serve |
| Font loading | 本地嵌入字型檔 | 離線使用，不依賴 CDN |
| Browser launch | 自動 `webbrowser.open()` | 非技術使用者不應看到 localhost |
| Server shutdown | 偵測無連線後自動關閉 | 關分頁 = 關程式 |
| Port | 隨機可用 port | 避免固定 port 衝突 |

## File Structure

```
gui/
├── web_app.py          # Flask app, routes, server lifecycle
├── static/
│   ├── css/
│   │   └── style.css   # 所有樣式，遵循 DESIGN.md
│   ├── js/
│   │   └── app.js      # 拖放、API 呼叫、即時更新、進度
│   └── fonts/          # DM Sans, Noto Sans TC, Geist Mono (woff2)
└── templates/
    └── index.html      # 單頁應用，所有 UI
```

舊的 `gui/app.py` 和 `gui/preview.py`（tkinter）將被刪除。

## API Endpoints

### `GET /`
Serve `index.html`。

### `POST /api/upload`
- Request: `multipart/form-data`，一或多個檔案
- Response: `{ "files": [{ "id": "uuid", "name": "學生名冊.xlsx", "size": 12345 }] }`
- 檔案存到 `tempfile.mkdtemp()`，server 關閉時清理

### `POST /api/preview`
即時預覽單一檔案的脫敏結果（不寫入磁碟）。
- Request: `{ "file_id": "uuid", "mode": "reversible"|"irreversible", "use_ner": false }`
- Response:
  ```json
  {
    "original": "陳美玲就讀國立臺北教育大學...",
    "anonymized": "__ANON:PERSON_001__就讀__ANON:SCHOOL_001__...",
    "spans": [
      { "start": 0, "end": 3, "text": "陳美玲", "category": "PERSON" },
      { "start": 5, "end": 13, "text": "國立臺北教育大學", "category": "SCHOOL" }
    ],
    "summary": { "PERSON": 3, "PHONE": 2, "EMAIL": 1, "ID": 2, "SCHOOL": 1 }
  }
  ```
- 圖片檔案：`original` 和 `anonymized` 為 base64 data URI（`data:image/png;base64,...`），`spans` 為空陣列，`summary` 包含 OCR 偵測到的類別計數

### `POST /api/process`
處理所有已上傳的檔案，寫入磁碟。
- Request: `{ "file_ids": ["uuid1", "uuid2"], "mode": "reversible", "use_ner": false }`
- Response: SSE (Server-Sent Events) 串流進度：
  ```
  data: { "type": "progress", "current": 1, "total": 5, "file": "學生名冊.xlsx" }
  data: { "type": "progress", "current": 2, "total": 5, "file": "教師通訊錄.docx" }
  data: { "type": "done", "results": [...], "output_dir": "/path/to/output" }
  ```

### `POST /api/batch`
批次處理整個資料夾。
- Request: `{ "folder": "/path/to/folder", "mode": "reversible", "use_ner": false }`
- Response: SSE 串流進度，同 `/api/process`

### `GET /api/download/<file_id>`
下載脫敏後的單一檔案。

### `POST /api/download-all`
打包所有已處理檔案為 zip 下載。

### `GET /api/config`
取得目前設定。

### `POST /api/config/import`
匯入設定 zip。

### `GET /api/config/export`
匯出設定 zip 下載。

### `GET /api/health`
Server heartbeat。前端每 30 秒 ping 一次，連續 3 次失敗則顯示「伺服器已關閉」。

## Frontend UI

單頁應用，所有互動透過 `fetch()` 打 API。

### Layout（遵循 DESIGN.md）

```
┌──────────────────────────────────────────────────┐
│  標題列：資料脫敏工具 Data Anonymizer             │
├──────────────────────────────────────────────────┤
│  工具列：[假名化|匿名化] [☐ NER] [開啟] [批次] [開始脫敏] │
├──────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────┐   │
│  │   拖放區：將檔案拖曳至此，或點擊選擇      │   │
│  └──────────────────────────────────────────┘   │
├──────────┬──────────────────┬────────────────────┤
│ 偵測摘要  │   原始內容        │   脫敏結果         │
│ 220px    │                  │                    │
│          │  PII 色彩高亮     │  Token 色彩標記     │
│ ● 姓名 12│                  │                    │
│ ■■■■■■■ │                  │                    │
│ ● 電話  5│                  │                    │
│ ■■■     │                  │                    │
│ ...      │                  │                    │
│          │                  │                    │
│ 共偵測 34 │                  │                    │
├──────────┴──────────────────┴────────────────────┤
│  狀態列：● 就緒  ████████ 3/5  v2.0.0            │
└──────────────────────────────────────────────────┘
```

### 互動流程

1. **拖放或點擊** — 檔案上傳到 `/api/upload`
2. **檔案出現在拖放區下方的檔案列表** — 點擊任一檔案觸發 `/api/preview`
3. **三欄即時更新** — 左側摘要（類別 + 條狀圖）、中間原文（PII 高亮）、右邊結果（Token 標記）
4. **按「開始脫敏」** — 呼叫 `/api/process`，SSE 串流更新進度條
5. **完成後** — 顯示成功 alert，可下載個別檔案或全部打包 zip

### 拖放實作

```
dragenter → 拖放區高亮（border-color: primary-light, bg: primary-bg）
dragover  → preventDefault
dragleave → 恢復原樣
drop      → 取得 files，POST 到 /api/upload
```

也支援 `<input type="file" multiple>` 點擊選擇。

### 進度更新

使用 `EventSource` (SSE) 監聽處理進度：
- 更新進度條寬度
- 更新狀態列文字（「處理中：學生名冊.xlsx 2/5」）
- 完成時顯示成功 alert

### 錯誤處理

- API 回傳 4xx/5xx → 顯示 error alert（紅色）
- 不支援的檔案格式 → 上傳時立即提示，不送到後端
- 網路中斷（health check 失敗）→ 顯示「伺服器已關閉，請重新啟動程式」

## Server Lifecycle

### 啟動流程

```python
def main():
    # 1. 找一個可用的 port
    port = find_free_port()

    # 2. 啟動 Flask（threaded=True，背景處理不阻塞 UI）
    server_thread = threading.Thread(
        target=app.run,
        kwargs={"port": port, "threaded": True},
        daemon=True
    )
    server_thread.start()

    # 3. 等 server ready
    wait_for_server(port)

    # 4. 開瀏覽器
    webbrowser.open(f"http://localhost:{port}")

    # 5. 監控連線，無人使用時自動關閉
    monitor_and_shutdown(port)
```

### 自動關閉

- 前端每 30 秒打 `/api/health`
- 後端紀錄最後一次 health check 時間
- 如果超過 2 分鐘沒有任何 request，清理 temp 檔案並 `sys.exit(0)`
- 使用者重新開啟 → 雙擊 exe 重新啟動

### 首次啟動 config 偵測

與現有邏輯相同：檢查 exe 同目錄是否有 `.anonymizer-config.zip`，有的話提示匯入。
改為前端的 modal dialog 取代 tkinter messagebox。

## Migration Plan

### 刪除的檔案
- `gui/app.py` (tkinter GUI)
- `gui/preview.py` (tkinter preview panel)

### 保留不動的檔案
- `anonymizer.py` — 核心引擎，完全不改
- `image_anonymizer.py` — 圖片引擎，不改
- `batch.py` — 批次處理，不改
- `config_manager.py` — 設定管理，不改
- `detectors/*` — 偵測器，不改
- `parsers/*` — 解析器，不改
- `mapping_manager.py` — 對照表，不改
- `updater.py` — 更新檢查，不改
- `models.py` — Span model，不改

### 修改的檔案
- `gui/__init__.py` — 更新 import
- `requirements.txt` — 加入 `flask>=3.0`
- `anonymizer.spec` — 更新 PyInstaller spec，加入 static/templates/fonts

### 新增的檔案
- `gui/web_app.py` — Flask app
- `gui/static/css/style.css`
- `gui/static/js/app.js`
- `gui/static/fonts/` — 字型檔
- `gui/templates/index.html`

## Dependencies

新增：
- `flask>=3.0` — web server

不需要：
- 不需要 build tools（no webpack, no npm）
- 不需要前端 framework（no React, no Alpine）
- 不需要 WebSocket library（用 SSE 就夠）

## Testing

- API endpoint 測試：用 Flask test client，不需要真的啟動 server
- 前端：手動 QA（拖放、預覽、處理流程、錯誤處理）
- PyInstaller 打包後測試：Windows VM 上雙擊 exe 驗證

## Out of Scope

- 多使用者同時使用（這是 localhost 單人工具）
- HTTPS（localhost 不需要）
- 資料庫（temp 檔案就夠）
- WebSocket（SSE 足夠處理進度更新）
- 前端路由（單頁就夠）
- i18n framework（介面只有繁體中文）
