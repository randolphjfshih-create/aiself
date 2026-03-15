# 🪞 思想代理人 · Soul Mirror MVP

> 一個基於 RAG（檢索增強生成）的個人「數位雙胞胎」，讓你能詢問過去的自己。

---

## 快速開始

### 1. 安裝依賴
```bash
pip install -r requirements.txt
```

### 2. 準備資料
在專案根目錄建立 `my_soul` 資料夾，並放入你的個人資料：
```
my_soul/
├── line_chat_2023.txt      # Line 對話記錄（匯出為純文字）
├── notes_2024.md           # 個人筆記
├── journal.pdf             # 日記 PDF
└── ...                     # 其他 .txt / .md / .pdf 檔案
```

> 💡 **Line 對話匯出方法：** 在聊天室右上角 → 其他 → 傳送聊天記錄 → 選擇純文字格式

### 3. 設定 API Key
方法一：環境變數（推薦）
```bash
export OPENAI_API_KEY="sk-your-key-here"
streamlit run app.py
```

方法二：在 Streamlit 側邊欄直接輸入 API Key

### 4. 啟動代理人
```bash
streamlit run app.py
```

---

## 功能說明

| 功能 | 說明 |
|------|------|
| **索引持久化** | 首次啟動會建立向量索引存入 `./storage`，之後直接載入，不重複消耗 API |
| **嚴格引用** | 代理人只根據你的資料回答，並標示引用來源 |
| **重新掃描** | 側邊欄按鈕可清除快取，重新讀取最新資料 |
| **繁體中文** | 全介面與回答預設繁體中文 |

---

## 架構說明

```
app.py
├── load_index()          # 建立或載入 LlamaIndex 向量索引
├── Sidebar               # API Key 輸入、索引狀態、檔案列表
├── Chat UI               # 聊天介面與歷史記錄
└── Query Engine          # similarity_top_k=5，引用來源節點
```

**System Prompt 核心設計：**
- 角色定位：使用者的數位思想代理人
- 嚴禁幻覺：無資料則坦承不知
- 強制引用：每個回答需標明來源
- 分析深度：聚焦價值觀、動機、思想演變

---

## 目錄結構

```
.
├── app.py              # 主程式
├── requirements.txt    # 依賴套件
├── my_soul/            # 你的個人資料（需自行建立）
└── storage/            # 向量索引快取（自動生成）
```

---

## 常見問題

**Q: 第一次啟動很慢？**
A: 正在為所有檔案建立向量嵌入，這是一次性操作，之後會直接載入快取。

**Q: 如何更新資料？**
A: 在 `my_soul` 中新增/修改檔案後，點選側邊欄的「重新掃描資料夾」按鈕。

**Q: 支援哪些檔案格式？**
A: `.txt`、`.md`、`.pdf`（包含子資料夾，遞迴讀取）。
