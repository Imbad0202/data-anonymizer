# Design System — 資料脫敏工具 Data Anonymizer

## Product Context
- **What this is:** 本地端個資偵測與脫敏工具，在傳送資料給 AI 工具或外部系統前，自動遮蔽 PII
- **Who it's for:** 學校行政人員，非技術背景，Windows 環境
- **Space/industry:** 資料隱私 / 教育行政，同類產品（TwLawBot、Redactable、Presidio）設計普遍粗糙
- **Project type:** 本地 Web UI（Python 後端 + HTML/CSS/JS 前端，localhost）

## Aesthetic Direction
- **Direction:** Industrial/Utilitarian + 亮色 — 專業工具感，像 Tableau 而非玩具
- **Decoration level:** Intentional — 用背景色和邊框區隔區塊，不用花俏裝飾
- **Mood:** 可信賴的專業工具。使用者打開後覺得「這東西是認真的」，操作後覺得「確實有把個資處理好」
- **Reference sites:** Airtable（親民的亮色 SaaS）、1Password（安全工具的信任感）、Protecto（隱私工具的專業感）

## Typography
- **Display/Hero:** DM Sans Bold — 現代幾何無襯線，專業但不冰冷
- **Body:** DM Sans Regular — 易讀、圓潤度適中
- **UI/Labels:** DM Sans Medium — 同家族，統一感
- **Data/Tables:** Geist Mono (tabular-nums) — token 顯示、對照表
- **CJK:** Noto Sans TC — 繁體中文最佳可讀性，與 DM Sans 搭配和諧
- **Code:** Geist Mono
- **Loading:** Google Fonts CDN（DM Sans, Noto Sans TC），本地打包時嵌入字型檔
- **Scale:**
  - xs: 11px — 狀態列、輔助標籤
  - sm: 13px — 側邊欄、按鈕、表單標籤
  - base: 14px — 內文、預覽文字
  - md: 15px — 卡片標題
  - lg: 18px — 區塊標題
  - xl: 24px — 頁面標題
  - 2xl: 32px — Hero 標題

## Color
- **Approach:** Restrained — 一個主色 + 中性灰 + 語義色 + PII 類別色
- **Primary:** `#0F766E` (teal-700) — 沉穩藍綠，傳達安全與信任
- **Primary Light:** `#14B8A6` (teal-500) — hover 狀態、強調
- **Primary BG:** `#F0FDFA` (teal-50) — 主色淺底
- **Surface:** `#F8FAFC` (slate-50) — 頁面底色
- **White:** `#FFFFFF` — 卡片、面板底色
- **Border:** `#E2E8F0` (slate-200) — 一般邊框
- **Border Strong:** `#CBD5E1` (slate-300) — 輸入框、分隔線
- **Text:** `#1E293B` (slate-800) — 主要文字
- **Text Secondary:** `#475569` (slate-600) — 次要文字
- **Muted:** `#64748B` (slate-500) — 輔助說明
- **Muted Light:** `#94A3B8` (slate-400) — placeholder

### PII Category Colors
每種 PII 類別有專屬顏色，用於高亮標記和側邊摘要：

| Category | Dot/Text | Background | 用途 |
|----------|----------|------------|------|
| PERSON 姓名 | `#3B82F6` blue-500 | `#DBEAFE` blue-100 | 人名偵測 |
| PHONE 電話 | `#EA580C` orange-600 | `#FED7AA` orange-200 | 電話號碼 |
| EMAIL | `#0D9488` teal-600 | `#CCFBF1` teal-100 | Email 地址 |
| ID 身分證 | `#DC2626` red-600 | `#FEE2E2` red-100 | 身分證字號 |
| SCHOOL 學校 | `#7C3AED` violet-600 | `#EDE9FE` violet-100 | 學校名稱 |
| FINANCE 金融 | `#CA8A04` yellow-600 | `#FEF9C3` yellow-100 | 信用卡、帳號 |
| URL | `#64748B` slate-500 | `#F1F5F9` slate-100 | 網址、IP |

### Semantic Colors
- **Success:** `#059669` bg `#D1FAE5` — 處理完成
- **Warning:** `#D97706` bg `#FEF3C7` — NER 載入中、注意事項
- **Error:** `#DC2626` bg `#FEE2E2` — 格式不支援、處理失敗

## Spacing
- **Base unit:** 8px
- **Density:** Comfortable — 學校行政人員需要大一點的點擊區域
- **Scale:** 2xs(2) xs(4) sm(8) md(16) lg(24) xl(32) 2xl(48) 3xl(64)

## Layout
- **Approach:** Grid-disciplined — 三欄主介面（側邊摘要 + Before + After）
- **Structure:**
  - 頂部：標題列（窗口標題）
  - 工具列：模式 toggle + NER checkbox + 檔案操作按鈕 + 開始脫敏
  - 拖放區：檔案拖入或點擊選擇
  - 主區域：左側偵測摘要(220px) | 中間原始內容 | 右邊脫敏結果
  - 底部：狀態列（狀態 + 進度條 + 版本號）
- **Max content width:** 不限（localhost 全寬）
- **Border radius:**
  - sm: 4px — 小元件（tag、dot）
  - md: 8px — 按鈕、輸入框、卡片
  - lg: 12px — 大容器、拖放區
  - full: 9999px — 圓形（狀態點）

## Motion
- **Approach:** Minimal-functional — 只做有意義的動態
- **Easing:** enter(ease-out) exit(ease-in) move(ease-in-out)
- **Duration:** micro(50-100ms) short(150-250ms) medium(250-400ms)
- **Where to use:**
  - 拖放區 hover/active 狀態變化（150ms）
  - 進度條填充動畫（300ms）
  - 按鈕 hover/active（150ms）
  - 輸入框 focus ring（150ms）
  - 不用：頁面轉場、彈跳動畫、載入骨架屏

## Shadows
- **sm:** `0 1px 2px rgba(0,0,0,0.05)` — toggle active、sidebar item hover
- **md:** `0 4px 6px -1px rgba(0,0,0,0.07), 0 2px 4px -2px rgba(0,0,0,0.05)` — 卡片
- **lg:** `0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -4px rgba(0,0,0,0.04)` — 主容器

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-29 | 亮色主題 | 學校辦公環境，使用者習慣亮色介面 |
| 2026-03-29 | Teal 主色 | 安全工具品類慣例（1Password 藍、Norton 綠），傳達信任 |
| 2026-03-29 | 色彩編碼 PII 類別 | 競品研究發現 Redactable 的色彩編碼最直覺，一眼辨識 |
| 2026-03-29 | 三欄佈局（摘要+Before+After） | 核心價值是「讓使用者看到脫敏在做什麼」，side-by-side 建立信任 |
| 2026-03-29 | DM Sans + Noto Sans TC | DM Sans 專業但不冷，Noto Sans TC 繁中最佳，兩者搭配和諧 |
| 2026-03-29 | 側邊欄條狀圖摘要 | Tableau 風格啟發，用資料視覺化提升專業感 |
| 2026-03-29 | Web UI 取代 tkinter | 外觀大幅提升，跨平台一致，PyInstaller 打包後開瀏覽器即用 |
| 2026-03-29 | Created by /design-consultation | 研究同類產品（Airtable, 1Password, Protecto, Redactable, Snagit），綜合提案 |
