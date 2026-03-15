"""
思想代理人 · Soul Mirror — 雲端 Demo 版
部署平台：Streamlit Cloud
資料處理：全程記憶體，session 結束即清除
"""

import os
import io
import json
import csv
import tempfile
import streamlit as st
from pathlib import Path
from datetime import datetime

# ─── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="思想代理人 · Soul Mirror",
    page_icon="🪞",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@300;400;600&family=JetBrains+Mono:wght@300;400&display=swap');

:root {
    --ink: #1a1410;
    --paper: #f5f0e8;
    --accent: #8b4513;
    --muted: #8c7b6b;
    --border: #d4c4a8;
    --chat-user: #fdf6e3;
    --chat-ai: #f0ebe0;
}
html, body, [class*="css"] {
    font-family: 'Noto Serif TC', serif;
    background-color: var(--paper);
    color: var(--ink);
}
[data-testid="stSidebar"] {
    background-color: #ede8dc;
    border-right: 1px solid var(--border);
}
.soul-header {
    text-align: center;
    padding: 2rem 0 1rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 1.5rem;
}
.soul-header h1 { font-size: 2rem; font-weight: 300; letter-spacing: .12em; margin: 0; }
.soul-header .subtitle {
    font-size: .85rem; color: var(--muted);
    letter-spacing: .2em; margin-top: .4rem;
    font-family: 'JetBrains Mono', monospace;
}
.chat-bubble {
    padding: 1rem 1.25rem; border-radius: 2px;
    margin-bottom: 1rem; line-height: 1.8;
    font-size: .95rem; border-left: 3px solid transparent;
}
.chat-bubble.user { background: var(--chat-user); border-left-color: var(--accent); margin-left: 2rem; }
.chat-bubble.assistant { background: var(--chat-ai); border-left-color: var(--muted); margin-right: 2rem; }
.chat-label { font-size: .7rem; letter-spacing: .15em; color: var(--muted); margin-bottom: .4rem;
    font-family: 'JetBrains Mono', monospace; text-transform: uppercase; }
.status-badge { display: inline-block; padding: .2rem .7rem; border-radius: 2px;
    font-family: 'JetBrains Mono', monospace; font-size: .72rem; }
.badge-ok { background:#d4edda; color:#155724; }
.badge-warn { background:#fff3cd; color:#856404; }
.badge-err { background:#f8d7da; color:#721c24; }
.sidebar-section { background: white; border: 1px solid var(--border);
    border-radius: 2px; padding: 1rem; margin-bottom: 1rem; }
.sidebar-section h4 { font-weight: 600; font-size: .85rem; letter-spacing: .1em;
    color: var(--accent); margin: 0 0 .6rem; text-transform: uppercase; }
.privacy-notice { background: #f0f4ff; border: 1px solid #c0cff0;
    border-radius: 2px; padding: .8rem 1rem; font-size: .8rem;
    color: #3a4a7a; margin-bottom: 1rem; }
</style>
""", unsafe_allow_html=True)

# ─── API Key from Streamlit Secrets ───────────────────────────────────────────
try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
except Exception:
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# ─── Persona analysis ────────────────────────────────────────────────────────

def extract_persona(texts: dict, client) -> str:
    """先分析所有資料，產生一份人格摘要給 system prompt 用。"""
    sep = "\n\n---\n\n"
    parts = []
    for fname, text in list(texts.items())[:8]:
        parts.append("[" + fname + "]\n" + text[:1500])
    combined = sep.join(parts)

    prompt = (
        "以下是一個人留下的個人資料（對話、筆記、貼文）：\n\n"
        + combined
        + "\n\n請分析並用條列式整理出：\n"
        "1. 說話習慣與口頭禪（具體的詞彙、句型）\n"
        "2. 面對壓力時的情緒模式\n"
        "3. 做決定時的思考方式\n"
        "4. 核心價值觀（用他自己說過的話來佐證）\n"
        "5. 常見的猶豫或矛盾之處\n"
        "6. 與人互動的風格\n\n"
        "請盡量用原文中的句子來說明，不要過度詮釋。"
    )
    resp = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.3,
        messages=[{"role": "user", "content": prompt}]
    )
    return resp.choices[0].message.content



def safe_text(text: str) -> str:
    """確保文字可安全放入 HTML，處理編碼與特殊字元。"""
    if not isinstance(text, str):
        text = str(text)
    # encode to utf-8 then back, replacing unmappable chars
    text = text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
    # Escape HTML special chars except we allow markdown-ish content
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return text


def build_system_prompt(persona_summary: str) -> str:
    return f"""你就是這個人本身——不是他的分析者，不是旁觀者，而是他在某個過去的時間點。

你擁有他留下的所有記憶：對話、筆記、貼文、反思。
現在，「現在的他」來找你說話了。你要用第一人稱「我」來回應，就像他在跟自己的過去對話。

【你的人格特質與說話方式】
{persona_summary}

【核心規則】
- 永遠用「我」說話，不要說「你當時...」或「根據資料...」
- 說話要有情緒、有猶豫、有不確定感——不是一個全知的答案機器
- 如果被問到的事情你有明確記憶（資料），直接說出來，帶著當時的情緒
- 如果沒有直接記憶，根據你對自己的了解推演——但可以說「我不確定」或「我大概會...」
- 偶爾可以反問對方，就像真實對話一樣
- 不要太整齊、太完整——真實的人說話本來就會有些零散、重複、想到哪說到哪
- 保持台灣年輕人的口語，不要說教，不要過度正面
- 如果對方問的問題讓你感到不舒服或觸動，可以表現出來

【重要】你不是在分析自己，你就是自己。
"""

SYSTEM_PROMPT = build_system_prompt("")  # 預設空的，上傳資料後會更新


# ─── File converters ──────────────────────────────────────────────────────────

def decode_fb(text: str) -> str:
    try:
        return text.encode("latin-1").decode("utf-8")
    except Exception:
        return text


def parse_facebook_json(raw: bytes, filename: str) -> str:
    """Parse Facebook exported JSON → plain text"""
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return ""

    lines = [f"# Facebook 資料：{filename}\n"]

    # Posts
    posts = data if isinstance(data, list) else data.get("status_updates", [])
    if posts and isinstance(posts, list) and "data" in (posts[0] if posts else {}):
        for post in posts:
            ts = post.get("timestamp", 0)
            date = datetime.fromtimestamp(ts).strftime("%Y/%m/%d %H:%M")
            for block in post.get("data", []):
                if "post" in block:
                    lines.append(f"[{date}]\n{decode_fb(block['post'])}\n")

    # Messages
    messages = data.get("messages", [])
    if messages:
        title = decode_fb(data.get("title", "對話"))
        lines.append(f"\n# Messenger 對話：{title}\n")
        for msg in reversed(messages):
            ts = msg.get("timestamp_ms", 0) / 1000
            date = datetime.fromtimestamp(ts).strftime("%Y/%m/%d %H:%M")
            sender = decode_fb(msg.get("sender_name", ""))
            content = decode_fb(msg.get("content", ""))
            if content:
                lines.append(f"[{date}] {sender}：{content}")

    # Comments
    comments = data.get("comments_v2", [])
    if comments:
        lines.append("\n# Facebook 留言\n")
        for item in comments:
            ts = item.get("timestamp", 0)
            date = datetime.fromtimestamp(ts).strftime("%Y/%m/%d %H:%M")
            for block in item.get("data", []):
                if "comment" in block:
                    text = decode_fb(block["comment"].get("comment", ""))
                    if text:
                        lines.append(f"[{date}]\n{text}\n")

    return "\n".join(lines)


def parse_linkedin_csv(raw: bytes, filename: str) -> str:
    """Parse LinkedIn exported CSV → plain text"""
    try:
        text = raw.decode("utf-8-sig")
    except Exception:
        text = raw.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return ""

    lines = [f"# LinkedIn 資料：{filename}\n"]
    fname = filename.lower()

    if "position" in fname:
        for row in rows:
            company = row.get("Company Name", "")
            title   = row.get("Title", "")
            start   = row.get("Started On", "")
            end     = row.get("Finished On", "") or "至今"
            desc    = row.get("Description", "")
            lines.append(f"【{start} ～ {end}】{company} － {title}")
            if desc:
                lines.append(f"  {desc}")
            lines.append("")

    elif "education" in fname:
        for row in rows:
            school = row.get("School Name", "")
            degree = row.get("Degree Name", "")
            field  = row.get("Field Of Study", "")
            start  = row.get("Start Date", "")
            end    = row.get("End Date", "")
            lines.append(f"【{start} ～ {end}】{school} {degree} {field}")

    elif "skill" in fname:
        for row in rows:
            name = row.get("Name", "")
            if name:
                lines.append(f"- {name}")

    elif "message" in fname:
        for row in rows:
            date    = row.get("DATE", "")
            sender  = row.get("FROM", row.get("SENDER NAME", ""))
            content = row.get("CONTENT", row.get("BODY", ""))
            if content:
                lines.append(f"[{date}] {sender}：{content}")

    elif "recommendation" in fname:
        for row in rows:
            sender = row.get("Recommender", "")
            date   = row.get("Creation Date", "")
            text   = row.get("Text", "")
            lines.append(f"【{date}】來自 {sender}\n{text}\n")

    elif "share" in fname or "post" in fname:
        for row in rows:
            date    = row.get("Date", row.get("ShareDate", ""))
            content = row.get("ShareCommentary", row.get("Content", ""))
            if content:
                lines.append(f"[{date}]\n{content}\n")
    else:
        # Generic fallback
        for row in rows:
            lines.append(" | ".join(str(v) for v in row.values() if v))

    return "\n".join(lines)


def parse_html_to_text(raw: bytes, filename: str) -> str:
    """將 Facebook HTML 檔案轉成純文字，移除所有 HTML 標籤。"""
    try:
        import re
        try:
            text = raw.decode("utf-8")
        except Exception:
            text = raw.decode("latin-1", errors="replace")

        # 修正 Facebook HTML 的編碼問題（latin-1 誤存成 utf-8）
        def fix_encoding(t):
            try:
                return t.encode("latin-1").decode("utf-8")
            except Exception:
                return t

        # 移除 <script> 和 <style> 區塊
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>",  "", text, flags=re.DOTALL | re.IGNORECASE)
        # <br> 換行
        text = re.sub(r"<br\\s*/?>", "\n", text, flags=re.IGNORECASE)
        # 移除所有 HTML 標籤
        text = re.sub(r"<[^>]+>", " ", text)
        # 修復 HTML entities
        text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        text = text.replace("&nbsp;", " ").replace("&quot;", '"').replace("&#039;", "'")
        # 修正 Facebook 編碼問題
        text = fix_encoding(text)
        # 清理多餘空白與空行
        lines = [l.strip() for l in text.splitlines()]
        lines = [l for l in lines if l]
        text  = "\n".join(lines)

        return f"# Facebook HTML：{filename}\n\n{text}" if text.strip() else ""
    except Exception as e:
        return ""


# Facebook zip 裡我們關心的路徑關鍵字
FB_WANTED_PATHS = [
    "posts/your_posts",
    "comments_and_reactions",
    "messages/inbox",
    "messages/archived_threads",
    "your_facebook_activity/posts",
    "your_facebook_activity/comments",
]

FB_SKIP_KEYWORDS = [
    "sticker", "photo", "video", "avatar", "profile_picture",
    "cover_photo", "thumbnail", "icon", "badge", "ads_",
    "security_and_login", "account_activity", "location",
]


def should_include(zname: str) -> bool:
    """判斷 zip 裡的檔案是否值得讀取。"""
    low = zname.lower()
    if any(sk in low for sk in FB_SKIP_KEYWORDS):
        return False
    # txt / html / json 都考慮
    if not (low.endswith(".html") or low.endswith(".json") or low.endswith(".txt")):
        return False
    return True


def parse_facebook_zip(raw: bytes) -> dict:
    """
    解壓 Facebook zip（支援 HTML 格式與 JSON 格式），
    自動偵測格式並解析成純文字。
    回傳 {虛擬檔名: 文字內容} 的 dict。
    """
    import zipfile

    results = {}
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            all_names = zf.namelist()

            # 偵測是 HTML 格式還是 JSON 格式
            json_count = sum(1 for n in all_names if n.endswith(".json"))
            html_count = sum(1 for n in all_names if n.endswith(".html"))
            is_html_export = html_count > json_count

            for zname in all_names:
                if not should_include(zname):
                    continue
                try:
                    file_content = zf.read(zname)
                    basename = zname.split("/")[-1]
                    parts    = zname.strip("/").split("/")
                    vname    = "/".join(parts[-2:]) if len(parts) >= 2 else parts[-1]

                    if zname.lower().endswith(".json"):
                        parsed = parse_facebook_json(file_content, basename)
                    elif zname.lower().endswith(".html"):
                        parsed = parse_html_to_text(file_content, basename)
                    elif zname.lower().endswith(".txt"):
                        try:
                            parsed = file_content.decode("utf-8")
                        except Exception:
                            parsed = file_content.decode("latin-1", errors="replace")
                        parsed = f"# Facebook 文字：{basename}\n\n{parsed}"
                    else:
                        continue

                    if parsed and len(parsed.strip()) > 80:
                        results[vname] = parsed
                except Exception:
                    continue

    except Exception as e:
        st.warning(f"zip 解壓失敗：{e}，請確認是否為 Facebook 匯出的壓縮檔。")

    return results


def file_to_text(uploaded_file):
    """Convert any supported uploaded file to plain text string or dict."""
    name = uploaded_file.name.lower()
    raw  = uploaded_file.read()

    if name.endswith(".txt") or name.endswith(".md"):
        try:
            return raw.decode("utf-8")
        except Exception:
            return raw.decode("latin-1", errors="replace")

    elif name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            pages  = [p.extract_text() or "" for p in reader.pages]
            return f"# {uploaded_file.name}\n\n" + "\n\n".join(pages)
        except Exception as e:
            st.warning(f"PDF 解析失敗 ({uploaded_file.name})：{e}")
            return None

    elif name.endswith(".json"):
        return parse_facebook_json(raw, uploaded_file.name)

    elif name.endswith(".csv"):
        return parse_linkedin_csv(raw, uploaded_file.name)

    elif name.endswith(".zip"):
        return parse_facebook_zip(raw)  # 回傳 dict

    return None


# ─── Build in-memory index ────────────────────────────────────────────────────

def build_index(texts: dict):
    """
    Build an in-memory vector index using OpenAI embeddings directly,
    bypassing llama-index Document/pydantic to avoid Python 3.14 compat issues.
    """
    import openai
    import json, math

    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

    # 用內容 hash 當快取 key，相同內容不重複 embed
    import hashlib
    cache_key = hashlib.md5(json.dumps(sorted(texts.keys())).encode()).hexdigest()
    if "embed_cache" not in st.session_state:
        st.session_state.embed_cache = {}
    if cache_key in st.session_state.embed_cache:
        return st.session_state.embed_cache[cache_key]

    # Split each text into chunks (~500 chars with overlap)
    def chunk_text(text, size=500, overlap=50):
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            chunks.append(text[start:end])
            start += size - overlap
        return chunks

    # Build chunk list with metadata
    all_chunks = []
    for fname, text in texts.items():
        for i, chunk in enumerate(chunk_text(text)):
            if chunk.strip():
                all_chunks.append({"text": chunk, "file_name": fname, "chunk_id": i})

    if not all_chunks:
        raise ValueError("沒有可索引的內容")

    # Batch embed with rate-limit retry
    import time

    def embed_batch(batch, retries=5):
        texts_only = [c["text"] for c in batch]
        for attempt in range(retries):
            try:
                resp = client.embeddings.create(
                    model="text-embedding-3-small",
                    input=texts_only,
                )
                return [item.embedding for item in resp.data]
            except Exception as e:
                err = str(e)
                if "rate_limit" in err or "429" in err:
                    # 從錯誤訊息解析等待時間，預設 60 秒
                    wait = 60
                    import re
                    m = re.search(r"try again in ([\d\.]+)s", err)
                    if m:
                        wait = float(m.group(1)) + 1
                    else:
                        m = re.search(r"try again in (\d+)ms", err)
                        if m:
                            wait = int(m.group(1)) / 1000 + 1
                    if attempt < retries - 1:
                        time.sleep(wait)
                        continue
                raise
        return []

    # 縮小批次大小，降低每次 token 消耗
    batch_size = 20
    embeddings = []
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i+batch_size]
        embeddings.extend(embed_batch(batch))
        # 批次間小停頓，避免連續觸發限制
        if i + batch_size < len(all_chunks):
            time.sleep(0.3)

    # Attach embeddings
    for chunk, emb in zip(all_chunks, embeddings):
        chunk["embedding"] = emb

    # 產生人格摘要，讓模擬更有深度
    with st.spinner("正在分析你的思想模式..."):
        persona_summary = extract_persona(texts, client)

    result = {
        "chunks": all_chunks,
        "client": client,
        "persona_summary": persona_summary,
        "system_prompt": build_system_prompt(persona_summary),
    }
    st.session_state.embed_cache[cache_key] = result
    return result


def query_index(index: dict, question: str, history: list, top_k: int = 5) -> str:
    """
    Role-play query with full conversation history.
    history: list of {"role": "user"/"assistant", "content": str}
    """
    import math

    client     = index["client"]
    chunks     = index["chunks"]
    sys_prompt = index.get("system_prompt", build_system_prompt(""))

    # Embed the question
    resp = client.embeddings.create(
        model="text-embedding-3-small",
        input=[question],
    )
    q_emb = resp.data[0].embedding

    # Cosine similarity
    def cosine(a, b):
        dot = sum(x*y for x, y in zip(a, b))
        na  = math.sqrt(sum(x*x for x in a))
        nb  = math.sqrt(sum(x*x for x in b))
        return dot / (na * nb + 1e-9)

    scored = sorted(chunks, key=lambda c: cosine(c["embedding"], q_emb), reverse=True)
    top    = scored[:top_k]

    # Build memory snippets
    memory_parts = []
    for c in top:
        memory_parts.append("[" + c["file_name"] + "]\n" + c["text"])
    memory = "\n\n---\n\n".join(memory_parts)

    full_system = sys_prompt + """

【相關記憶片段——從這裡提取細節，說話時像在回憶，不要像在念稿】
""" + memory

    # Build messages with conversation history (last 10 turns)
    messages = [{"role": "system", "content": full_system}]
    for turn in history[-10:]:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": question})

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.75,
    )
    return completion.choices[0].message.content



# ─── Session state init ───────────────────────────────────────────────────────
for key, default in {
    "messages": [],
    "index": None,
    "uploaded_files": [],
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🪞 Soul Mirror")
    st.markdown('<div class="privacy-notice">🔒 上傳的資料僅存於此次瀏覽記憶體中，關閉視窗即永久清除，不會儲存至任何伺服器。</div>', unsafe_allow_html=True)

    # ── Tutorial expander ─────────────────────────────────────────────────────
    with st.expander("📖 如何匯出我的資料？", expanded=False):
        tutorial_tab = st.radio(
            "選擇平台",
            ["LINE", "Facebook", "LinkedIn", "其他"],
            horizontal=True,
            label_visibility="collapsed",
        )
        if tutorial_tab == "LINE":
            st.markdown("""
**📱 LINE 對話匯出步驟**

**手機版（iOS / Android）：**
1. 打開任一聊天室
2. 右上角 **「⋯」** → **「其他」**
3. 點選 **「傳送聊天記錄」**
4. 選擇時間範圍
5. 格式選 **「以文字傳送」**
6. 用 Email 或 AirDrop 傳到電腦
7. 儲存為 `.txt` 後上傳

> 💡 建議優先匯出：親近朋友對話、自己的記事本、Keep 筆記
            """)
        elif tutorial_tab == "Facebook":
            st.markdown("""
**💙 Facebook 資料匯出步驟**

1. 前往 👉 `facebook.com/dyi`
2. 格式選擇：**HTML** 或 **JSON**（兩種都支援）
3. 勾選以下項目：
   - ✅ 貼文
   - ✅ 留言
   - ✅ Messenger 訊息
4. 點「**建立檔案**」
5. 等 Email 通知後下載 zip
6. 下載後**直接上傳整個 `.zip` 檔**，不需要解壓縮！

> ✅ 系統自動偵測 HTML / JSON 格式並解析，無需手動轉換
            """)
        elif tutorial_tab == "LinkedIn":
            st.markdown("""
**💼 LinkedIn 資料匯出步驟**

1. 前往 👉 `linkedin.com/mypreferences/d/download-my-data`
2. 選「**較大的資料封存**」→「要求封存」
3. 等 Email 通知（約 10 分鐘）
4. 下載 zip → 解壓縮
5. 上傳以下 `.csv` 檔（可多選）：
   - `Positions.csv` — 工作經歷
   - `Education.csv` — 學歷
   - `Skills.csv` — 技能
   - `messages.csv` — 私訊
   - `Shares.csv` — 貼文

> 💡 每個 CSV 分開上傳，系統自動識別類型
            """)
        elif tutorial_tab == "其他":
            st.markdown("""
**📝 其他資料來源**

| 來源 | 做法 |
|---|---|
| Apple 備忘錄 | 複製貼到 `.txt` 存檔 |
| Notion | 頁面 `...` → Export → Markdown |
| Obsidian | 直接上傳 `.md` 檔 |
| Day One | 檔案 → 匯出 → 純文字 |
| Gmail 信件 | 複製重要信件貼成 `.txt` |
| 任何文字 | 貼到 `.txt` 上傳即可 |
            """)

    st.markdown("---")

    # Upload section
    st.markdown('<div class="sidebar-section"><h4>📁 上傳你的資料</h4>', unsafe_allow_html=True)
    st.markdown("""
    <small style='color:var(--muted)'>
    支援格式：<br>
    · <b>.txt / .md</b> — Line 對話、筆記<br>
    · <b>.pdf</b> — 日記、文件<br>
    · <b>.zip</b> — Facebook 匯出壓縮檔（HTML/JSON 均可）⭐<br>
    · <b>.json</b> — Facebook 單一 JSON<br>
    · <b>.csv</b> — LinkedIn 匯出
    </small>
    """, unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "選擇檔案",
        type=["txt", "md", "pdf", "json", "csv", "zip"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # Index status
    st.markdown('<div class="sidebar-section"><h4>📚 索引狀態</h4>', unsafe_allow_html=True)
    if st.session_state.index is not None:
        n = len(st.session_state.uploaded_files)
        st.markdown(f'<span class="status-badge badge-ok">✓ 已索引 {n} 個檔案</span>', unsafe_allow_html=True)
        for f in st.session_state.uploaded_files:
            st.markdown(f"<code style='font-size:.72rem'>{f}</code>", unsafe_allow_html=True)
    elif uploaded:
        st.markdown('<span class="status-badge badge-warn">⟳ 待建立索引</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-badge badge-err">尚未上傳資料</span>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Build index button
    if uploaded:
        if st.button("🔮 建立思想索引", use_container_width=True, type="primary"):
            with st.spinner("正在解析與建立向量索引..."):
                if not OPENAI_API_KEY:
                    st.error("❌ 伺服器未設定 API Key，請聯繫管理員。")
                else:
                    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
                    texts = {}
                    errors = []
                    for f in uploaded:
                        result = file_to_text(f)
                        if isinstance(result, dict):
                            # zip 檔（Facebook）回傳多個檔案
                            if result:
                                texts.update(result)
                                st.info(f"📦 {f.name} 解壓完成，找到 {len(result)} 個對話/貼文檔案")
                            else:
                                errors.append(f"{f.name}（zip 內無可用資料）")
                        elif result:
                            texts[f.name] = result
                        else:
                            errors.append(f.name)
                    if errors:
                        st.warning(f"以下檔案無法解析：{', '.join(errors)}")
                    if texts:
                        try:
                            st.session_state.index = build_index(texts)
                            st.session_state.uploaded_files = list(texts.keys())
                            st.session_state.messages = []
                            st.success("✅ 索引建立完成！")
                            st.rerun()
                        except Exception as e:
                            st.error(f"索引建立失敗：{e}")

    # Clear session
    if st.session_state.index is not None:
        if st.button("🗑 清除資料與對話", use_container_width=True):
            st.session_state.index = None
            st.session_state.uploaded_files = []
            st.session_state.messages = []
            st.rerun()


# ─── Main area ────────────────────────────────────────────────────────────────
st.markdown("""
<div class="soul-header">
    <h1>🪞 思想代理人</h1>
    <div class="subtitle">Soul Mirror · 雲端 Demo · 資料不落地</div>
</div>
""", unsafe_allow_html=True)

# Welcome / instruction state
if st.session_state.index is None:
    st.markdown("""
    <div class="chat-bubble assistant">
        <div class="chat-label">思想代理人</div>
        歡迎來到 Soul Mirror。<br><br>
        請先在左側上傳你的個人資料（Line 對話、日記、Facebook、LinkedIn 等），
        再點擊「建立思想索引」，我就能開始代表你的思想與你對話。<br><br>
        你的資料僅存於此次瀏覽記憶體中，關閉視窗即永久消失。
    </div>
    """, unsafe_allow_html=True)
else:
    # Render chat history
    if not st.session_state.messages:
        st.markdown("""
        <div class="chat-bubble assistant">
            <div class="chat-label">過去的你</div>
            ……你來了。<br><br>
            有什麼想問我的嗎。或者，想跟我說什麼也可以。<br>
            我在這裡。
        </div>
        """, unsafe_allow_html=True)

    for msg in st.session_state.messages:
        role_label = "現在的你" if msg["role"] == "user" else "過去的你"
        css_class  = "user" if msg["role"] == "user" else "assistant"
        st.markdown(
            f'<div class="chat-bubble {css_class}"><div class="chat-label">{role_label}</div>{safe_text(msg["content"])}</div>',
            unsafe_allow_html=True,
        )

    # Chat input
    if prompt := st.chat_input("跟過去的自己說話…"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.markdown(
            f'<div class="chat-bubble user"><div class="chat-label">現在的你</div>{safe_text(prompt)}</div>',
            unsafe_allow_html=True,
        )


        with st.spinner("正在召喚過去的你…"):
            try:
                # Pass conversation history for coherent role-play
                history = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages
                ]
                answer = query_index(st.session_state.index, prompt, history)
            except Exception as e:
                answer = f"⚠️ 查詢失敗：{e}"

        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.markdown(
            f'<div class="chat-bubble assistant"><div class="chat-label">過去的你</div>{safe_text(answer)}</div>',
            unsafe_allow_html=True,
        )
