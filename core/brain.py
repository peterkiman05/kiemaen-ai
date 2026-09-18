import httpx
import sqlite3
import base64
import json
import os
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
    c.execute("INSERT INTO memory (role, content) VALUES (?, ?)", (role, content))
    c.execute("DELETE FROM memory WHERE rowid NOT IN (SELECT rowid FROM memory ORDER BY rowid DESC LIMIT 40)")
    conn.commit()
    conn.close()

def retrieve_memory():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role, content FROM memory ORDER BY rowid ASC")
    rows = c.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in rows]

def encode_image(image_bytes):
    return base64.b64encode(image_bytes).decode('utf-8')

def get_best_model(groq_api_key, is_vision=False):
    url = "https://api.groq.com/openai/v1/models"
    headers = {"Authorization": f"Bearer {groq_api_key}"}
    available = []
    
    try:
        response = httpx.get(url, headers=headers, timeout=10.0)
        if response.status_code == 200:
            models = response.json().get("data", [])
            available = [m["id"] for m in models]
    except Exception as e:
        print(f"[Brain] Error fetching models: {e}")

    preferred_chat = [
        "llama-3.3-70b-versatile", "llama-3.3-70b-specdec", "llama3-70b-8192", 
        "llama-3.1-8b-instant", "llama3-8b-8192", "gemma2-9b-it", 
        "gemma-7b-it", "mixtral-8x7b-32768", "llama-3.2-3b-preview"
    ]
    preferred_vision = ["llama-3.2-11b-vision-preview", "llama-3.2-90b-vision-preview"]

    target_list = preferred_vision if is_vision else preferred_chat

    # Strict match against known working models
    for model in target_list:
        if model in available:
            print(f"[Brain] Model selected: {model}")
            return model

    # Blind fallback excluding toxic/audio models
    if available:
        for m in available:
            m_lower = m.lower()
            if "guard" not in m_lower and "whisper" not in m_lower and "canopy" not in m_lower:
                print(f"[Brain] Auto-Fallback model selected: {m}")
                return m
                
    return target_list[0]

# Renamed back to ask_kiemaen to match main.py expectations. 
# Added **kwargs to catch any extra arguments main.py might try to pass.
def ask_kiemaen(prompt, image_bytes=None, **kwargs):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise Exception("GROQ_API_KEY not found in environment or .env file.")

    init_db()
    history = retrieve_memory()
    
    is_vision = image_bytes is not None
    model = get_best_model(api_key, is_vision)
    
    messages = [{"role": "system", "content": "You are Kiemaen, an advanced AI running locally on Termux Android. Provide code solutions cleanly."}]
    messages.extend(history)

    if is_vision:
        base64_image = encode_image(image_bytes)
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]
        })
    else:
        messages.append({"role": "user", "content": prompt})

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "temperature": 0.7}

    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=60.0)
        response.raise_for_status()
        ai_text = response.json()["choices"][0]["message"]["content"]
        
        store_memory("user", prompt)
        store_memory("assistant", ai_text)
        return ai_text
    except Exception as e:
        err_msg = str(e)
        if 'response' in locals(): err_msg += f" | Details: {response.text}"
        raise Exception(f"Groq API Error: {err_msg}")

