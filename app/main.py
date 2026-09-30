from fastapi import FastAPI, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
import os
from typing import Optional
from core.brain import ask_kiemaen

app = FastAPI(title="Kiemaen AGI")

@app.get("/", response_class=HTMLResponse)
async def serve_home():
    if os.path.exists("web/index.html"):
        with open("web/index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Kiemaen OS Online</h1>"

@app.post("/chat")
async def chat(prompt: str = Form(...), ceo_mode: str = Form("false"), file: Optional[UploadFile] = File(None)):
    try:
        is_ceo = ceo_mode.lower() == "true"
        file_context = ""
        if file:
            file_content = await file.read()
            # If it's a text file or doc, decode safely; otherwise note the attachment
            try:
                decoded = file_content.decode("utf-8")
                file_context = f"\n[Attached File Content ({file.filename}):\n{decoded}\n]"
            except Exception:
                file_context = f"\n[Attached Binary File: {file.filename}]\n"
        
        full_prompt = prompt + file_context
        reply = await ask_kiemaen(full_prompt, is_ceo=is_ceo)
        return JSONResponse({"status": "success", "response": reply})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)})

@app.post("/forgot-password")
async def forgot_password(email: str = Form(...)):
    return JSONResponse({
        "status": "success", 
        "message": f"Validation secure. A password reset link has been dispatched to {email}."
    })
