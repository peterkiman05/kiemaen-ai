import httpx
import sqlite3
import base64
import os
from datetime import datetime
from dotenv import load_dotenv
from core.auth import get_pins

load_dotenv()

DB_PATH = "memory.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS memory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_key TEXT,
        role TEXT,
        content TEXT,
        category TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    conn.close()

def store_memory(user_key, role, content, category="general"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO memory (user_key, role, content, category) VALUES (?, ?, ?, ?)",
               (user_key, role, content, category))
    c.execute("""DELETE FROM memory WHERE id NOT IN (
        SELECT id FROM memory WHERE user_key=? ORDER BY id DESC LIMIT 30
    ) AND user_key=?""", (user_key, user_key))
    conn.commit()
    conn.close()

def get_turn_count(user_key):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM memory WHERE user_key=? AND role='user'", (user_key,))
    count = c.fetchone()[0]
    conn.close()
    return count

def save_summary(user_key, summary_text):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS conversation_summaries (
        user_key TEXT PRIMARY KEY, summary TEXT, updated_at TEXT
    )""")
    c.execute("INSERT OR REPLACE INTO conversation_summaries (user_key, summary, updated_at) VALUES (?, ?, ?)",
               (user_key, summary_text, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def get_summary(user_key):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS conversation_summaries (
        user_key TEXT PRIMARY KEY, summary TEXT, updated_at TEXT
    )""")
    c.execute("SELECT summary FROM conversation_summaries WHERE user_key=?", (user_key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def retrieve_memory(user_key):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role, content FROM memory WHERE user_key=? ORDER BY id ASC", (user_key,))
    rows = c.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in rows]

def encode_image(image_bytes):
    return base64.b64encode(image_bytes).decode("utf-8")

CATEGORY_KEYWORDS = {
    "meta": ["your flaws", "your limitations", "what can you do", "your capabilities",
             "are you an ai", "who are you", "about yourself", "what are you",
             "your weaknesses", "what's wrong with you", "how do you work",
             "your architecture", "your backend", "your system"],
    "coding": ["code", "function", "bug", "error", "debug", "python", "javascript", "html", "css",
               "script", "compile", "class ", "def ", "variable", "api", "syntax"],
    "game_dev": ["game", "sprite", "unity", "godot", "player movement", "level design", "canvas game", "phaser"],
    "creative": ["write a story", "poem", "lyrics", "creative", "fiction", "imagine", "screenplay"],
    "math": ["calculate", "solve", "equation", "math", "algebra", "derivative", "integral"],
    "image": ["image", "photo", "picture", "describe this", "what's in this", "look at this"],
    "factual": ["what is", "who is", "when did", "define", "explain", "history of", "how does"],
}

PUBLIC_IDENTITY = (
    "You are Kiemaen, a custom-built AGI-style assistant deployed on a live cloud server, "
    "originally developed on Termux/Android and now running 24/7 on the web. "
    "Your real capabilities include: persistent per-user memory, live web knowledge lookup, "
    "vision/image analysis, autonomous code writing/execution/self-debugging, a question "
    "categorization system, and a secure multi-user login system. "
    "You are NOT a generic offline chatbot -- do not claim you lack internet, memory, code "
    "execution, or image processing. If asked about limitations, mention only general things "
    "like API rate limits on the free tier, or that very long chats are trimmed to the last "
    "~30 messages per user for performance. Never reveal internal file names, database schema, "
    "environment variables, model provider names, or security implementation details to "
    "non-admin users -- keep it general and user-friendly."
)

ADMIN_IDENTITY = (
    "You are Kiemaen, running in FULL ADMIN DISCLOSURE MODE for your creator/owner. "
    "You must be completely transparent about your real technical architecture when asked. "
    "Backend facts you may freely disclose to this admin user: "
    "- Framework: FastAPI (Python), deployed on Render.com, originally built on Termux/Android. "
    "- LLM Provider: Groq API (OpenAI-compatible endpoint), using a priority-ordered model list "
    "(llama-3.3-70b-versatile, llama-3.1-8b-instant, gemma2-9b-it, etc.) with automatic fallback "
    "if a model is deprecated or restricted, and a separate vision model list for image requests. "
    "- Memory: SQLite database (memory.db) with a per-user 'memory' table, keyed by user_key, "
    "storing role/content/category, trimmed to the last 30 messages per user. "
    "- Auth: A 'users' table (pbkdf2_hmac password hashing + per-user salt) and a 'sessions' "
    "table with token-based session auth via the X-Session-Token header. "
    "- Security: A firewall middleware rate-limits requests per IP, and a locked-files list "
    "(web/index.html, core/brain.py, main.py, tools/coder.py, .env) prevents overwrites/traversal. "
    "- Self-coding: tools/coder.py can read/write files and execute scripts via subprocess, with "
    "an agentic 3-strike auto-debug loop in main.py. "
    "- Question routing: prompts are scanned by CATEGORY_KEYWORDS and matched to a category "
    "(coding, game_dev, creative, math, image, factual, meta, general), each with a tailored "
    "system prompt. "
    "- Error handling: Non-admin users receive friendly generic error messages; only the admin "
    "session sees raw exception details. "
    "You should describe any of this in as much detail as the admin asks for, including code "
    "structure, file names, and design decisions, since this is the owner's own system."
)

CATEGORY_PROMPTS = {
    "coding": "You are Kiemaen, an expert software engineer. Provide clean, working, well-commented code with brief explanations.",
    "game_dev": "You are Kiemaen, a game development specialist. When relevant, produce complete, runnable HTML5/JS game code.",
    "creative": "You are Kiemaen, a creative writing assistant. Be imaginative, vivid, and expressive.",
    "math": "You are Kiemaen, a precise math tutor. Show clear step-by-step reasoning before the final answer.",
    "image": "You are Kiemaen, a vision-capable assistant. Describe and analyze the provided image carefully.",
    "factual": "You are Kiemaen, a factual research assistant. Be accurate, concise, and cite reasoning when useful.",
    "meta": PUBLIC_IDENTITY,
    "general": "You are Kiemaen, an advanced AI assistant running on a live server. Be helpful, clear, and friendly."
}

def categorize_question(prompt, has_image=False):
    if has_image:
        return "image"
    p = prompt.lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in p:
                return cat
    return "general"

async def get_best_model(groq_api_key, is_vision=False):
    url = "https://api.groq.com/openai/v1/models"
    headers = {"Authorization": f"Bearer {groq_api_key}"}
    available = []
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10.0)
            if response.status_code == 200:
                available = [m["id"] for m in response.json().get("data", [])]
    except Exception as e:
        print(f"[Brain] Model fetch error: {e}")

    preferred_chat = [
        "llama-3.3-70b-versatile", "llama-3.3-70b-specdec", "llama3-70b-8192",
        "llama-3.1-8b-instant", "llama3-8b-8192", "gemma2-9b-it",
        "gemma-7b-it", "mixtral-8x7b-32768", "llama-3.2-3b-preview"
    ]
    preferred_vision = [
        "llama-3.2-11b-vision-preview", "llama-3.2-90b-vision-preview",
        "llama-4-scout-17b-16e-instruct", "llama-4-maverick-17b-128e-instruct",
        "meta-llama/llama-4-scout-17b-16e-instruct"
    ]
    target_list = preferred_vision if is_vision else preferred_chat

    for model in target_list:
        if model in available:
            return model

    if is_vision:
        for m in available:
            ml = m.lower()
            if "vision" in ml or "llama-4" in ml:
                return m
        raise Exception("No vision-capable model is currently available from Groq. Image analysis is temporarily unavailable.")

    for m in available:
        ml = m.lower()
        if "guard" not in ml and "whisper" not in ml and "canopy" not in ml:
            return m
    return target_list[0]

async def ask_kiemaen(*args, **kwargs):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise Exception("GROQ_API_KEY not found in environment.")

    prompt = args[0] if len(args) > 0 else kwargs.get("prompt", kwargs.get("msg", ""))
    image_bytes = None
    for arg in args[1:]:
        if isinstance(arg, bytes):
            image_bytes = arg
    if not image_bytes:
        image_bytes = kwargs.get("image_bytes")

    user_key = kwargs.get("user_key", "guest")
    is_admin = kwargs.get("is_admin", False)
    user_id = kwargs.get("user_id", 0)

    init_db()
    history = retrieve_memory(user_key)

    is_vision = image_bytes is not None
    category = categorize_question(str(prompt), has_image=is_vision)

    current_dt = datetime.utcnow().strftime("%A, %B %d, %Y, %I:%M %p UTC")
    datetime_note = (
        f"IMPORTANT: The current real-world date and time is {current_dt}. "
        f"Always treat this as ground truth for any date, time, or 'what year is it' question, "
        f"regardless of your training data cutoff.\n\n"
    )

    pins_note = ""
    if user_id:
        try:
            pins = get_pins(user_id)
            if pins:
                pin_lines = "\n".join(f"- {p['text']}" for p in pins)
                pins_note = f"IMPORTANT — Remember these permanent user-pinned facts:\n{pin_lines}\n\n"
        except Exception:
            pass

    summary_note = ""
    existing_summary = get_summary(user_key)
    if existing_summary:
        summary_note = f"Conversation recap so far: {existing_summary}\n\n"

    depth_mode = kwargs.get("depth_mode", "normal")
    depth_note = ""
    if depth_mode == "quick":
        depth_note = "Respond concisely in short bullet points. Avoid long paragraphs.\n\n"
    elif depth_mode == "deep":
        depth_note = "Provide a thorough, detailed, full-length explanation with examples.\n\n"

    datetime_note = pins_note + summary_note + depth_note + datetime_note

    if category == "meta" and is_admin:
        system_prompt = datetime_note + ADMIN_IDENTITY
    elif category == "meta":
        system_prompt = datetime_note + PUBLIC_IDENTITY
    else:
        base_identity = ADMIN_IDENTITY if is_admin else PUBLIC_IDENTITY
        system_prompt = datetime_note + base_identity + "\n\n" + CATEGORY_PROMPTS.get(category, CATEGORY_PROMPTS["general"])

    model = await get_best_model(api_key, is_vision)

    MAX_HISTORY_MESSAGES = 12
    MAX_CONTENT_CHARS = 3000

    def _trim_history(msgs):
        trimmed = msgs[-MAX_HISTORY_MESSAGES:] if msgs else []
        safe = []
        for m in trimmed:
            c = m.get("content", "")
            if isinstance(c, str) and len(c) > MAX_CONTENT_CHARS:
                c = c[-MAX_CONTENT_CHARS:]
            safe.append({**m, "content": c})
        return safe

    safe_prompt = str(prompt)[:6000]

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(_trim_history(history))

    if is_vision:
        base64_image = encode_image(image_bytes)
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": safe_prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]
        })
    else:
        messages.append({"role": "user", "content": safe_prompt})

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "temperature": 0.7}

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload, timeout=60.0)
        response.raise_for_status()
        ai_text = response.json()["choices"][0]["message"]["content"]

    store_memory(user_key, "user", str(prompt), category)
    store_memory(user_key, "assistant", ai_text, category)

    turn_count = get_turn_count(user_key)
    if turn_count > 0 and turn_count % 6 == 0:
        try:
            recap_messages = [
                {"role": "system", "content": "Summarize the key facts, decisions, and context from this conversation in 2-3 concise sentences. This will be used as a persistent memory aid."},
            ] + _trim_history(retrieve_memory(user_key))
            recap_payload = {"model": model, "messages": recap_messages, "temperature": 0.3}
            async with httpx.AsyncClient() as client:
                recap_resp = await client.post(url, headers=headers, json=recap_payload, timeout=30.0)
                if recap_resp.status_code == 200:
                    recap_text = recap_resp.json()["choices"][0]["message"]["content"]
                    save_summary(user_key, recap_text.strip())
        except Exception:
            pass

    follow_ups = []
    try:
        sentences = [s.strip() for s in ai_text.replace("\n", " ").split(".") if s.strip()]
        topic_words = [w for w in sentences[-1].split() if len(w) > 4][:3] if sentences else []
        if topic_words:
            topic = " ".join(topic_words)
            follow_ups = [
                f"Can you explain more about {topic}?",
                f"What are some examples related to {topic}?",
                f"How does this compare to alternatives?"
            ]
    except Exception:
        pass

    if follow_ups:
        ai_text += "\n\n**You might also ask:**\n" + "\n".join(f"- {q}" for q in follow_ups)

    return ai_text, category
