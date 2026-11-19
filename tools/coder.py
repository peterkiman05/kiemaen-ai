import os
import subprocess
import re

def read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"[ERROR] {e}"

def write_file(path: str, content: str) -> bool:
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception as e:
        return False

def extract_code(text: str) -> str:
    matches = re.findall(r"```(?:python)?\s*([\s\S]*?)```", text)
    if matches:
        return matches[0].strip()
    return text.strip()

def run_script(path: str):
    try:
        result = subprocess.run(["python3", path], capture_output=True, text=True, timeout=10)
        output = result.stdout + result.stderr
        success = result.returncode == 0
        return output, success
    except Exception as e:
        return str(e), False
