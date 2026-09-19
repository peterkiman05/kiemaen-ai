import os
from fastapi import FastAPI, Form, File, UploadFile, Header
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv

from core.brain import ask_kiemaen
from core.auth import (init_auth_db, ensure_admin_exists, create_user, verify_user,
                        create_session, get_session_user, delete_session)
from core.security import firewall_middleware, is_path_safe
from tools.coder import read_file, write_file, extract_code, run_script

load_dotenv()

app = FastAPI()
app.middleware("http")(firewall_middleware)

init_auth_db()
ensure_admin_exists()

def get_user(token):
    if not token:
        return {"id": 0, "username": "guest", "is_admin": False}
    user = get_session_user(token)
    if not user:
        return {"id": 0, "username": "guest", "is_admin": False}
    return user

@app.get("/")
async def home():
    return FileResponse("web/index.html")

@app.post("/register")
async def register(username: str = Form(...), password: str = Form(...)):
    if len(username) < 3 or len(password) < 4:
        return {"status": "error", "message": "Username or password too short."}
    ok = create_user(username, password)
    if not ok:
        return {"status": "error", "message": "Username already taken."}
    user = verify_user(username, password)
    token = create_session(user["id"])
    return {"status": "ok", "token": token, "username": user["username"], "is_admin": user["is_admin"]}

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    user = verify_user(username, password)
    if not user:
        return {"status": "error", "message": "Invalid username or password."}
    token = create_session(user["id"])
    return {"status": "ok", "token": token, "username": user["username"], "is_admin": user["is_admin"]}

@app.post("/logout")
async def logout(x_session_token: str = Header(default=None)):
    if x_session_token:
        delete_session(x_session_token)
    return {"status": "ok"}

@app.get("/me")
async def me(x_session_token: str = Header(default=None)):
    user = get_user(x_session_token)
    return {"username": user["username"], "is_admin": user["is_admin"]}

@app.post("/chat")
async def chat(
    prompt: str = Form(default=""),
    msg: str = Form(default=""),
    image: UploadFile = File(default=None),
    x_session_token: str = Header(default=None)
):
    user = get_user(x_session_token)
    user_key = f"user_{user['id']}" if user["id"] else "guest"
    is_admin = user["is_admin"]

    text = prompt or msg
    image_bytes = await image.read() if image else None

    try:
        if image_bytes:
            reply, category = await ask_kiemaen(text, image_bytes, user_key=user_key, is_admin=is_admin)
        else:
            reply, category = await ask_kiemaen(text, user_key=user_key, is_admin=is_admin)

        if "```" in reply and any(k in text.lower() for k in ["run", "execute", "test this", "debug"]):
            file_name = "sandbox_script.py"
            if is_path_safe(file_name):
                code = extract_code(reply)
                write_file(file_name, code)
                out, success = run_script(file_name)
                if not success:
                    reply += f"\n\n**(Execution Failed - Initiating Autonomous Fix)**:\n```\n{out}\n```"
                    fix_prompt = f"The code you just wrote in {file_name} failed with this error:\n{out}\nPlease output ONLY the fully corrected code."
                    fix_reply, _ = await ask_kiemaen(fix_prompt, user_key=user_key, is_admin=is_admin)
                    fixed_code = extract_code(fix_reply)
                    write_file(file_name, fixed_code)
                    out2, success2 = run_script(file_name)
                    reply += f"\n\n**(Agentic Fix Applied)**: {'Success' if success2 else 'Failed'}.\n```\n{out2}\n```"

        return {"status": "ok", "response": reply, "category": category}

    except Exception as e:
        err_str = str(e)
        if is_admin:
            return JSONResponse(status_code=200, content={"status": "error", "message": f"[ADMIN DEBUG] {err_str}"})
        else:
            if "too large" in err_str.lower() or "413" in err_str:
                friendly = "Your message or file is too large. Please shorten it and try again."
            elif "rate" in err_str.lower() or "429" in err_str:
                friendly = "Kiemaen is a bit busy right now. Please try again in a few seconds."
            else:
                friendly = "Something went wrong on my end. Please try rephrasing your message."
            return JSONResponse(status_code=200, content={"status": "error", "message": friendly})
