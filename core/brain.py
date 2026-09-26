import httpx
import sqlite3
import base64
import os
import asyncio
import io
from PIL import Image
from dotenv import load_dotenv

load_dotenv()
DB_PATH = "memory.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS memory USING fts5(role, content)""")
    conn.commit()
    conn.close()

def store_memory(role, content):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    safe_content = content[:600] if len(content) > 600 else content
    c.execute("INSERT INTO memory (role, content) VALUES (?, ?)", (role, safe_content))
    c.execute("DELETE FROM memory WHERE rowid NOT IN (SELECT rowid FROM memory ORDER BY rowid DESC LIMIT 2)")
    conn.commit()
    conn.close()

def retrieve_memory():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role, content FROM memory ORDER BY rowid ASC")
    rows = c.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in rows]

def compress_image(image_bytes: bytes) -> str:
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail((600, 600))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=70)
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception as e:
        return base64.b64encode(image_bytes).decode('utf-8')

def select_persona(prompt: str) -> str:
    p_lower = prompt.lower()
    
    # Absolute Architectural Truth (Prevents self-disclosure hallucinations)
    base_truth = (
        "You are Kiemaen, an advanced personal AGI assistant running locally on Android via Termux. "
        "Your true and only codebase architecture consists of: FastAPI in 'main.py', core logic and database handlers in 'core/brain.py' and 'core/auth.py', "
        "SQLite databases ('memory.db' and 'auth.db'), and coding tools in 'tools/coder.py'. "
        "Never hallucinate non-existent files like config.py or tools/vision.py. Be direct, factual, and efficient."
    )

    if any(k in p_lower for k in ["beam", "stress", "shear", "calculus", "mechanics", "study", "formula", "equation", "material", "math"]):
        return base_truth + " You are also Kiemaen Study Tutor, an expert civil engineering assistant. Use LaTeX ($formula$) for math and give step-by-step derivations."
    elif any(k in p_lower for k in ["game", "pygame", "loop", "sprite", "render", "canvas", "collider"]):
        return base_truth + " You are Kiemaen Game Architect. Write robust Python game code using Pygame or lightweight canvas rendering, handling delta timing and clean input loops."
    elif any(k in p_lower for k in ["publish", "store", "itch", "steam", "pypi", "release", "version", "readme"]):
        return base_truth + " You are Kiemaen Software Publishing Advisor. Provide structured guidance on packaging, versioning, README docs, and distribution requirements."
    elif any(k in p_lower for k in ["code", "python", "fastapi", "bug", "script", "debug", "api", "git", "termux"]):
        return base_truth + " You are Kiemaen Software Architect, an expert full-stack developer running on Termux. Write clean, robust code with error handling."
    else:
        return base_truth

async def get_available_model(api_key, is_vision=False):
    url = "https://api.groq.com/openai/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                models = [m["id"] for m in data if "whisper" not in m["id"] and "guard" not in m["id"] and "embedding" not in m["id"]]
                if is_vision:
                    vision_candidates = [m for m in models if "vision" in m or "qwen" in m]
                    if vision_candidates:
                        return vision_candidates[0]
                if models:
                    return models[0]
    except Exception:
        pass
    return "openai/gpt-oss-20b" if not is_vision else "llama-3.2-11b-vision-preview"

async def ask_kiemaen(*args, **kwargs):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise Exception("GROQ_API_KEY not found in environment or .env file.")

    prompt = args[0] if len(args) > 0 else kwargs.get("prompt", kwargs.get("msg", ""))
    image_bytes = None
    doc_text = kwargs.get("doc_text", None)

    for arg in args[1:]:
        if isinstance(arg, bytes):
            image_bytes = arg
    if not image_bytes:
        image_bytes = kwargs.get("image_bytes")

    init_db()
    is_vision = image_bytes is not None
    model = await get_available_model(api_key, is_vision)

    system_persona = select_persona(str(prompt))
    
    user_content = str(prompt)
    if doc_text:
        if len(doc_text) > 3000:
            doc_text = doc_text[:3000] + "\n[Truncated...]"
        user_content = f"--- Attached Doc ---\n{doc_text}\n--------------------\n\nRequest: {prompt}"

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    last_error = "No connection attempted"
    
    for use_history in [True, False]:
        history = retrieve_memory() if use_history else []
        messages = [{"role": "system", "content": system_persona}]
        messages.extend(history)

        if is_vision:
            base64_image = compress_image(image_bytes)
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": user_content},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            })
        else:
            messages.append({"role": "user", "content": user_content})

        payload = {"model": model, "messages": messages, "temperature": 0.7}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=60.0)
                if response.status_code == 429:
                    await asyncio.sleep(2)
                    continue
                if response.status_code in [404, 400, 413]:
                    last_error = f"Model {model} status {response.status_code}: {response.text}"
                    model = "openai/gpt-oss-20b"
                    continue
                response.raise_for_status()
                ai_text = response.json()["choices"][0]["message"]["content"]
                store_memory("user", str(prompt))
                store_memory("assistant", ai_text)
                return ai_text, "general"
        except Exception as e:
            last_error = str(e)
            continue

    raise Exception(f"Smart Router Dynamic Error: {last_error}")
