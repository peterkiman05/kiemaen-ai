import os
import difflib
from fastapi import FastAPI, Form, File, UploadFile, Cookie, Response, Request, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv

from core.brain import ask_kiemaen
from core.database import get_db
from core.models import User
from core.auth import (
    login_user, 
    logout_user, 
    refresh_token_endpoint, 
    verify_user_account, 
    require_admin, 
    get_current_user,
    verify_user_credentials,
    create_session, get_session_user, delete_session,
    create_pending_verification, verify_and_create_user,
    get_user_email, create_login_code, verify_login_code,
    get_user_by_username, log_admin_alert, get_admin_alerts,
    add_pin, get_pins, remove_pin, add_task, get_tasks, complete_task, revoke_all_sessions
)
from core.mailer import send_verification_email
from core.security import (firewall_middleware, is_path_safe, is_locked_file,
                            propose_edit, confirm_edit, reject_edit, rollback_edit,
                            validate_python_syntax, LOCKED_FILES)
from core.evolution import AUTHORIZE_EVOLUTION_TOKEN, verify_evolution_token
from tools.coder import read_file, write_file, extract_code, run_script
from tools.registry import register_custom_tool, list_custom_tools
from sqlalchemy import select

load_dotenv()

# ==========================================
# 1. INITIALIZE FASTAPI APP & FIREWALL
# ==========================================
app = FastAPI()
app.middleware("http")(firewall_middleware)

# ==========================================
# 2. PRODUCTION AUTHENTICATION ENDPOINTS
# ==========================================
@app.post("/auth/login")
async def api_login(request: Request, response: Response, user_key: str = Form(...), password: str = Form(...), totp_code: str = Form(None), db: AsyncSession = Depends(get_db)):
    return await login_user(db, response, request, user_key, password, totp_code)

@app.post("/auth/refresh")
async def api_refresh(request: Request, response: Response, refresh_token: str = Form(...), db: AsyncSession = Depends(get_db)):
    return await refresh_token_endpoint(db, request, response, refresh_token)

@app.post("/auth/verify")
async def api_verify(user_key: str = Form(...), code: str = Form(...), db: AsyncSession = Depends(get_db)):
    return await verify_user_account(db, user_key, code)

@app.post("/auth/logout")
async def api_logout(response: Response, db: AsyncSession = Depends(get_db), current_user = Depends(get_current_user)):
    return await logout_user(db, response, current_user=current_user)

@app.get("/admin/users")
async def admin_list_users(db: AsyncSession = Depends(get_db), admin = Depends(require_admin)):
    result = await db.execute(select(User))
    users = result.scalars().all()
    return [{
        "user_key": u.user_key,
        "role": u.role,
        "mfa_enabled": u.mfa_enabled,
        "locked_until": u.locked_until,
        "last_login_at": u.last_login_at
    } for u in users]

# ==========================================
# 3. CORE APP ROUTES & CAPABILITIES
# ==========================================

@app.post("/register/request-code")
async def register_request_code(username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    if len(username) < 3 or len(password) < 4:
        return {"status": "error", "message": "Username or password too short."}
    code, error = create_pending_verification(username, email, password)
    if error:
        return {"status": "error", "message": error}
    send_verification_email(email, code, username)
    return {"status": "ok", "message": f"Verification code sent to {email}."}


def issue_session_cookie(response: Response, user_id, username, is_admin):
    token = create_session(user_id)
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=86400,
        path="/"
    )
    return {"status": "ok", "username": username, "is_admin": is_admin}

@app.post("/register/verify")
async def register_verify(response: Response, email: str = Form(...), code: str = Form(...)):
    user, error = verify_and_create_user(email, code)
    if error:
        return {"status": "error", "message": error}
    return issue_session_cookie(response, user["id"], user["username"], user["is_admin"])

@app.post("/login/request")
async def login_request(username: str = Form(...), password: str = Form(...)):
    user = verify_user_credentials(username, password)
    if not user:
        return {"status": "error", "message": "Invalid username or password."}
    email = get_user_email(username)
    if not email:
        return {"status": "error", "message": "No email associated with this account."}
    code = create_login_code(username)
    send_verification_email(email, code, username)
    return {"status": "otp_required", "message": f"Login code sent to {email}."}

@app.post("/login/verify")
async def login_verify(response: Response, username: str = Form(...), code: str = Form(...)):
    success, result = verify_login_code(username, code)
    if not success:
        return {"status": "error", "message": result}
    user = result
    return issue_session_cookie(response, user["id"], user["username"], user["is_admin"])

@app.get("/")
async def home():
    return FileResponse("web/index.html")

@app.get("/me")
async def me(session_token: str = Cookie(default=None)):
    user = get_session_user(session_token)
    if not user:
        return {"status": "ok", "username": "Guest", "is_admin": False}
    return {"status": "ok", "username": user["username"], "is_admin": user["is_admin"]}

@app.get("/capabilities")
async def capabilities():
    return {
        "status": "ok",
        "architecture": ["main.py", "core/brain.py", "core/auth.py", "core/evolution.py", "tools/coder.py"],
        "database": ["memory.db (FTS5)", "auth.db (SQLAlchemy Async)"],
        "ai_provider": "Groq API (Dynamic Model Discovery)",
        "capabilities": [
            "Local Termux execution",
            "Argon2id password hashing & JWT cookies",
            "Universal document & image parsing",
            "Step-by-step LaTeX civil engineering & math tutoring",
            "Game coding & Pygame loop support",
            "Software publishing guidance",
            "Daily task planner & persistent notebook",
            "Admin-restricted auto-evolution pipeline"
        ]
    }

@app.post("/chat")
async def chat(
    prompt: str = Form(default=""),
    msg: str = Form(default=""),
    file: UploadFile = File(default=None),
    image: UploadFile = File(default=None),
    session_token: str = Cookie(default=None)
):
    user = get_session_user(session_token) or {"id": 0, "username": "Guest", "is_admin": False}
    user_key = f"user_{user['id']}" if user["id"] else "guest"
    is_admin = user["is_admin"]

    text = prompt or msg
    image_bytes = await image.read() if image else None
    
    doc_text = None
    if file:
        file_bytes = await file.read()
        try:
            doc_text = file_bytes.decode('utf-8', errors='ignore')
        except Exception:
            doc_text = f"[Binary file uploaded: {file.filename}]"

    try:
        stripped_cmd = text.strip()

        if stripped_cmd.upper().startswith("AUTHORIZE_EVOLUTION"):
            if not is_admin:
                return {"status": "ok", "response": "⛔ **Access Denied**: Auto-evolution features are restricted to administrators.", "category": "meta"}
            parts = stripped_cmd.split()
            if len(parts) >= 2 and verify_evolution_token(parts[1]):
                return {"status": "ok", "response": "🧬 **Evolution Authorized Successfully**: Background patch pipeline unlocked.", "category": "meta"}
            return {"status": "ok", "response": "❌ Invalid or expired evolution authorization token.", "category": "meta"}

        if stripped_cmd.upper() == "LOGOUT_ALL_DEVICES":
            revoke_all_sessions(user["id"])
            return {"status": "ok", "response": "All your active sessions have been revoked.", "category": "meta"}

        if stripped_cmd.upper().startswith("TASK:"):
            task_title = stripped_cmd[5:].strip()
            if task_title and user["id"]:
                add_task(user["id"], task_title)
                return {"status": "ok", "response": f"Task added to your Daily Planner: \"{task_title}\"", "category": "meta"}

        if stripped_cmd.upper() == "SHOW_TASKS":
            if not user["id"]:
                return {"status": "ok", "response": "Please log in to manage tasks.", "category": "meta"}
            tasks = get_tasks(user["id"])
            if not tasks:
                return {"status": "ok", "response": "No tasks in your daily planner.", "category": "meta"}
            lines = [f"[{t['id']}] ({t['status']}) {t['title']}" for t in tasks]
            return {"status": "ok", "response": "**Your Daily Tasks:**\n\n" + "\n".join(lines), "category": "meta"}

        if stripped_cmd.upper().startswith("DONE_TASK"):
            parts = stripped_cmd.split()
            if len(parts) >= 2 and parts[1].isdigit() and user["id"]:
                complete_task(user["id"], int(parts[1]))
                return {"status": "ok", "response": f"Task {parts[1]} marked as completed.", "category": "meta"}

        reply, category = await ask_kiemaen(text, image_bytes, doc_text=doc_text, user_key=user_key, is_admin=is_admin, user_id=user["id"])
        return {"status": "ok", "response": reply, "category": category}

    except Exception as e:
        return JSONResponse(status_code=200, content={"status": "error", "message": f"[ERROR] {str(e)}"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8081, reload=True)
