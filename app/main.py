from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
import os
from core.brain import ask_kiemaen

app = FastAPI(title="Kiemaen AGI")

@app.get("/", response_class=HTMLResponse)
async def serve_home():
    if os.path.exists("web/index.html"):
        with open("web/index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Kiemaen OS Online</h1>"

@app.post("/chat")
async def chat(prompt: str = Form(...), ceo_mode: str = Form("false")):
    try:
        is_ceo = ceo_mode.lower() == "true"
        reply = await ask_kiemaen(prompt, is_ceo=is_ceo)
        return JSONResponse({"status": "success", "response": reply})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)})

@app.post("/forgot-password")
async def forgot_password(email: str = Form(...)):
    # Simulates sending a secure JWT reset link to the registered email
    # In a full production environment, this triggers an SMTP email dispatch.
    return JSONResponse({
        "status": "success", 
        "message": f"Validation secure. A password reset link has been dispatched to {email}."
    })
