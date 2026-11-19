import os
import json
import subprocess
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

# ================== CONFIG ==================
# Using requests directly bypasses the need for the broken 'openai' package on Termux
API_KEY = os.getenv("GROQ_API_KEY")
API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.1-8b-instant"
MEMORY_FILE = "jarvis_memory.json"

# ================== TTS (Speak) ==================
def speak(text):
    """Speak using Android TTS (Termux:API)."""
    print(f"\nJarvis: {text}")
    clean = text.replace("*", "").replace("#", "").replace("`", "")
    subprocess.run(["termux-tts-speak", clean])

# ================== STT (Listen) ==================
def listen():
    """Convert speech to text using Android's Native Engine"""
    print("\n[Listening... Speak now!]")
    try:
        result = subprocess.run(
            ["termux-speech-to-text"], 
            capture_output=True, 
            text=True
        )
        text = result.stdout.strip()
        print(f"You: {text}")
        return text
    except Exception as e:
        print(f"Transcription error: {e}")
        return ""

# ================== MEMORY ==================
def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_memory(messages):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(messages[-20:], f, indent=2, ensure_ascii=False)

# ================== THINK (Brain - USING REQUESTS NOW) ==================
def think(prompt, system_extra=""):
    if not API_KEY:
        return "Error: GROQ_API_KEY is not set in your .env file."
        
    memory = load_memory()
    system_prompt = f"""You are Jarvis, a personal AI assistant running on Android Termux.
You are concise, helpful, and practical.
Your specialties: Coding, Debugging, Explaining, Fixing.
Give clean, readable answers. {system_extra} If the user asks to set an alarm, you MUST reply with the exact time wrapped in brackets like this: [ALARM:HH:MM] in 24-hour format. Example: 'Setting alarm. [ALARM:07:00]'"""

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(memory)
    messages.append({"role": "user", "content": prompt})
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 2500
    }
    
    try:
        # Direct API call, no OpenAI library needed!
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status() # Check for errors (like 401 Unauthorized)
        
        reply = response.json()["choices"][0]["message"]["content"]

        # Save to memory
        memory.append({"role": "user", "content": prompt})
        memory.append({"role": "assistant", "content": reply})
        save_memory(memory)
        return reply
    except Exception as e:
        return f"Brain error: {e}"

# ================== CODE TOOLS ==================
def read_file(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

def write_file(path, content):
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Saved to: {path}"
    except Exception as e:
        return f"Error writing file: {e}"

def extract_code_block(text):
    if "```" not in text:
        return text
    parts = text.split("```")
    for i in range(1, len(parts), 2):
        block = parts[i]
        if "\n" in block:
            first_line = block.split("\n", 1)[0]
            if first_line.strip().isalpha() or first_line.strip() == "":
                return block.split("\n", 1)[1]
        return block
    return text

def debug_code(file_path):
    speak(f"Analyzing {file_path} for bugs")
    code = read_file(file_path)
    if code.startswith("Error"):
        return code

    prompt = f"""You are an expert debugger. Analyze this code:
1. Find ALL bugs
2. Explain each bug in SIMPLE terms
3. Give me the FULLY CORRECTED, working code in a single markdown block.

Code from `{file_path}`:
```python
{code}
```"""
    resp = think(prompt)
    fixed = extract_code_block(resp)

    base, ext = os.path.splitext(file_path)
    fixed_path = f"{base}_fixed{ext}"
    write_file(fixed_path, fixed)
    return resp + f"\n\n---\nSaved fixed code: {fixed_path}"

def run_python(file_path):
    speak(f"Running {file_path}")
    try:
        result = subprocess.run(
            [sys.executable, file_path],
            capture_output=True,
            text=True,
            timeout=120
        )
        output = ""
        if result.stdout:
            output += f"OUTPUT:\n{result.stdout}\n"
        if result.stderr:
            output += f"ERRORS:\n{result.stderr}\n"
        if not output:
            output = "Program ran with no output."
        return f"Exit code: {result.returncode}\n\n{output}"
    except subprocess.TimeoutExpired:
        return "Error: Script timed out (2 minutes)"
    except Exception as e:
        return f"Error running: {e}"

# ================== MAIN LOOP ==================
def run_jarvis():
    speak("System online. Good morning.")
    
    while True:
        input("\nPress [ENTER] to speak to Jarvis...")
        command = listen().lower()
        
        if not command:
            continue
            
        if "shut down" in command or "sleep" in command:
            speak("Powering down. Goodbye.")
            break
            
        elif "debug" in command:
            speak("Type the name of the file you want to debug:")
            file_to_debug = input("Filename (e.g. script.py): ")
            result = debug_code(file_to_debug)
            print(f"\n{result}")
            speak("I have finished debugging the file.")
            
        elif "run code" in command or "execute" in command:
            speak("Type the name of the file you want to run:")
            file_to_run = input("Filename: ")
            result = run_python(file_to_run)
            print(f"\n{result}")
            speak("Execution complete. Check the terminal for output.")
            
        else:
            response = think(command)
            speak(response)

if __name__ == "__main__":
    run_jarvis()
