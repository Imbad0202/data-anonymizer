# 範例一：基本文字脫敏

## 使用者需求

> 我有一段包含學生個資的文字，需要在傳送給 AI 之前脫敏處理。

## 假名化模式（可還原）

假名化會將敏感資訊替換為 `__ANON:CATEGORY_NNN__` 格式的 token，並產生對照表供事後還原。

```python
from anonymizer import Anonymizer

config = {
    "custom_terms": {
        "schools": ["國立台灣大學", "台大"],
        "departments": ["資訊工程學系"],
    },
    "substring_match": True,
}

anon = Anonymizer(
    config=config,
    session_id="demo-session",
    use_ner=False,       # False = 僅用自訂詞彙 + 正則，速度快
    reversible=True,     # True = 假名化，可還原
)

text = "學生王小明就讀國立台灣大學資訊工程學系，手機 0912-345-678，Email: wang@ntu.edu.tw"
result, summary = anon.anonymize_text(text)
```

### 輸出

**脫敏結果：**
```
學生 __ANON:PERSON_001__ 就讀 __ANON:SCHOOL_001____ANON:DEPARTMENT_001__，手機 __ANON:PHONE_001__，Email: __ANON:EMAIL_001__
```

**摘要：**
```
已脫敏：DEPARTMENT 1 個、EMAIL 1 個、PERSON 1 個、PHONE 1 個、SCHOOL 1 個
```

## 匿名化模式（不可逆）

匿名化使用通用標記 `[CATEGORY]` 替換，無法還原原始值，符合台灣個資法規範。

```python
anon = Anonymizer(
    config=config,
    session_id="demo-session",
    use_ner=False,
    reversible=False,    # False = 匿名化，不可逆
)

result, summary = anon.anonymize_text(text)
```

### 輸出

**脫敏結果：**
```
學生 [PERSON] 就讀 [SCHOOL][DEPARTMENT]，手機 [PHONE]，Email: [EMAIL]
```

## 啟用 NER 偵測

加入 ckip-transformers NER 可偵測未在自訂詞彙中的人名與組織名，但需要較長載入時間。

```python
anon = Anonymizer(
    config=config,
    session_id="demo-session",
    use_ner=True,        # 啟用 NER（首次載入模型需 10-30 秒）
    reversible=True,
)

# NER 可額外偵測到未列入自訂詞彙的人名
text = "陳教授在會議中提到林同學的論文"
result, summary = anon.anonymize_text(text)
# 「陳教授」和「林同學」中的姓名部分會被 NER 偵測
```

## 偵測引擎執行順序

三層偵測引擎依以下順序執行，重疊區間由長度優先規則解決：

1. **Custom Terms**（自訂詞彙）— 完全匹配或子字串匹配
2. **Regex**（正則表達式）— Email、電話、身分證字號、URL
3. **NER**（命名實體辨識）— ckip-transformers 繁體中文模型

當多個偵測器對同一段文字產生重疊的 Span 時，系統優先保留較長的 Span，再依來源優先順序（custom > ner > regex）排序。
