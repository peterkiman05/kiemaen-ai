from fastapi import FastAPI, Form, UploadFile, File
from fastapi.responses import FileResponse
from core.brain import ask_kiemaen
from tools.coder import read_file, write_file, extract_code, run_script, search_web
import os

app = FastAPI()

@app.get("/")
def home(): return FileResponse("web/index.html")

@app.post("/chat")
async def chat_endpoint(msg: str = Form(...), image: UploadFile = File(None)):
    try:
        context = ""
        msg_lower = msg.lower()
        img_bytes = await image.read() if image else None
        
        file_name = "app_module.py" 
        for word in msg_lower.split():
            if "." in word: file_name = word; break
            
        protected = ["web/index.html", "core/brain.py", "main.py", "tools/coder.py", ".env"]
        is_protected = file_name in protected or ".." in file_name or file_name.startswith("/")
        
        # WEB SCRAPING RE-ENGINEERED (Wikipedia fallback for clean text)
        if "search" in msg_lower or "today" in msg_lower or "current" in msg_lower or "price" in msg_lower:
            search_query = msg.replace("search", "").replace("for", "").strip()
            web_data = search_web(search_query)
            context += f"[LIVE WEB DATA]:\n{web_data}\n"

        if "read file" in msg_lower:
            context += f"[FILE CONTENTS of {file_name}]:\n{read_file(file_name)}\n"
        
        # 1. Ask AI First (So it can write the code BEFORE we run it)
        reply = await ask_kiemaen(msg, context, img_bytes)
        
        # 2. Extract & Save Code
        trigger_words = ["build", "create", "write", "debug", "fix"]
        code_saved = False
        if "```" in reply and any(w in msg_lower for w in trigger_words) and not is_protected:
            code = extract_code(reply)
            if code != reply:
                write_file(file_name, code)
                code_saved = True
                reply += f"\n\n*(System: Saved to {file_name})*"

        # 3. Agentic Loop (Run the file we just saved)
        if "run" in msg_lower and code_saved:
            out, success = run_script(file_name)
            if success:
                reply += f"\n\n**(Execution Success)**:\n```\n{out}\n```"
            else:
                # Code failed! Autonomously send it back to the AI for a fix.
                reply += f"\n\n**(Execution Failed - Initiating Autonomous Fix)**:\n```\n{out}\n```"
                fix_prompt = f"The code you just wrote in {file_name} failed with this error:\n{out}\nPlease output ONLY the fully corrected code."
                fix_reply = await ask_kiemaen(fix_prompt)
                
                fixed_code = extract_code(fix_reply)
                write_file(file_name, fixed_code)
                out2, success2 = run_script(file_name)
                
                reply += f"\n\n**(Agentic Fix Applied)**: The bug was identified and rewritten. New Execution Result: {'Success' if success2 else 'Failed'}.\n```\n{out2}\n```"
                
        return {"reply": reply}
    except Exception as e:
        return {"reply": f"[SYSTEM SHIELD] Internal error: {str(e)}"}
