import os
import importlib.util

TOOLS_DIR = "custom_tools"

def register_custom_tool(name: str, code: str) -> bool:
    try:
        os.makedirs(TOOLS_DIR, exist_ok=True)
        filename = f"{name.lower().strip().replace(' ', '_')}.py"
        filepath = os.path.join(TOOLS_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)
        return True
    except Exception as e:
        print(f"[Tool Registry Error] {e}")
        return False

def list_custom_tools():
    if not os.path.exists(TOOLS_DIR):
        return []
    return [f[:-3] for f in os.listdir(TOOLS_DIR) if f.endswith(".py")]
