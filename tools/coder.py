import os
import subprocess
import sys
import urllib.request
import json

def read_file(path):
    try:
        with open(path, "r") as f: return f.read()
    except Exception as e: return f"[ERROR] {e}"

def write_file(path, content):
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f: f.write(content)
        return f"Saved to {path}"
    except Exception as e: return f"[ERROR] {e}"

def extract_code(text):
    if "```" not in text: return text
    parts = text.split("```")
    for i in range(1, len(parts), 2):
        block = parts[i]
        if "\n" in block: return block.split("\n", 1)[1]
        return block
    return text

def run_script(path):
    try:
        res = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=10)
        output = f"OUT:\n{res.stdout}\n"
        if res.stderr: output += f"ERR:\n{res.stderr}"
        return output.strip(), res.returncode == 0
    except Exception as e: return f"[ERROR] {e}", False

def search_web(query):
    """Fallback search using Wikipedia API which is never blocked by Captchas."""
    try:
        safe_query = urllib.parse.quote(query)
        url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={safe_query}&utf8=&format=json"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib.request.urlopen(req).read()
        data = json.loads(response)
        
        results = ""
        for item in data['query']['search'][:3]:
            clean_text = item['snippet'].replace('<span class="searchmatch">', '').replace('</span>', '').replace('&quot;', '"')
            results += f"- {item['title']}: {clean_text}\n"
            
        return results if results else "Web search yielded no relevant data. You must rely on internal knowledge."
    except Exception as e:
        return "Live data unavailable."
