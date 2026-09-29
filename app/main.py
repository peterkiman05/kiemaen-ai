# System hardware rule injection
SYSTEM_ALARM_INSTRUCTION = " You are an autonomous AI connected to an Android phone. If the user asks to set an alarm or wake up, you MUST include the tag [ALARM:HH:MM] in 24-hour format in your response (e.g. [ALARM:07:00])."

import sqlite3
import os
import inspect
from contextlib import asynccontextmanager
from fastapi import FastAPI, Form, File, UploadFile, Cookie, Response, Request, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv
from pydantic import BaseModel

from core.brain import ask_kiemaen
from core.database import get_db
from core.models import User
from core.auth import (
    login_user, logout_user, refresh_token_endpoint, verify_user_account,
    require_admin, get_current_user, verify_user_credentials,
    create_session, get_session_user, delete_session,
    create_pending_verification, verify_and_create_user,
    get_user_email, create_login_code, verify_login_code,
    get_user_by_username, log_admin_alert, get_admin_alerts,
    add_pin, get_pins, remove_pin, add_task, get_tasks, complete_task, revoke_all_sessions
)
from core.mailer import send_verification_email
from core.security import firewall_middleware, is_path_safe, is_locked_file, propose_edit, confirm_edit, reject_edit, rollback_edit, validate_python_syntax, LOCKED_FILES
from core.evolution import AUTHORIZE_EVOLUTION_TOKEN, verify_evolution_token
from tools.coder import read_file, write_file, extract_code, run_script
from tools.registry import register_custom_tool, list_custom_tools
from sqlalchemy import select

# Import Enterprise Agents (Kim, Kit, Kat)
from app.agents.kim import Kim
from app.agents.kit import Kit
from app.agents.kat import Kat

load_dotenv()

def get_kiemaen_db():
    conn = sqlite3.connect("kiemaen.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, user_key TEXT UNIQUE, email TEXT, password_hash TEXT, role TEXT DEFAULT 'user', verification_code TEXT, verification_expires REAL)")
    try: cursor.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE users ADD COLUMN verification_code TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE users ADD COLUMN verification_expires REAL")
    except: pass
    cursor.execute("CREATE TABLE IF NOT EXISTS pending_verifications (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, email TEXT, password TEXT, code TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, token TEXT UNIQUE, user_id INTEGER)")
    conn.commit()
    return conn

def init_db():
    conn = get_kiemaen_db()
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, user_key TEXT UNIQUE, email TEXT, password TEXT, role TEXT DEFAULT 'user')")
    cursor.execute("CREATE TABLE IF NOT EXISTS pending_verifications (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, email TEXT, password TEXT, code TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, token TEXT UNIQUE, user_id INTEGER)")
    conn.commit()
    conn.close()

@asynccontextmanager
async def lifespan(app):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)
app.middleware("http")(firewall_middleware)

# Initialize Enterprise Agents
agent_kim = Kim()
agent_kit = Kit()
agent_kat = Kat()

# ==========================================
# AUTHENTICATION & REGISTRATION ENDPOINTS
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
        key="session_token", value=token, httponly=True, secure=False, samesite="lax", max_age=86400, path="/"
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
    return FileResponse("static/web/index.html")

@app.get("/me")
async def me(session_token: str = Cookie(default=None)):
    user = get_session_user(session_token)
    if not user:
        return {"status": "ok", "username": "Guest", "is_admin": False}
    return {"status": "ok", "username": user["username"], "is_admin": user["is_admin"]}

# ==========================================
# CHAT & AGENT ROUTING ENGINE
# ==========================================
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
    stripped_cmd = text.strip()
    image_bytes = await image.read() if image else None

    doc_text = None
    if file:
        file_bytes = await file.read()
        try:
            doc_text = file_bytes.decode('utf-8', errors='ignore')
        except Exception:
            doc_text = f"[Binary file uploaded: {file.filename}]"

    try:
        # Autonomous Agent Command Routing (Manager capability)
        if stripped_cmd.lower().startswith("tell kim") or stripped_cmd.lower().startswith("ask kim"):
            pair = "XAUUSD" if "xauusd" in stripped_cmd.lower() else "Active Asset"
            res = agent_kim.execute_trade(pair, "Vault Markets")
            return {"status": "ok", "response": f"☘️ **Kim (Trading Ops):** {res}", "category": "meta"}
            
        if stripped_cmd.lower().startswith("tell kit") or stripped_cmd.lower().startswith("ask kit"):
            target = stripped_cmd.split("kit", 1)[1].strip()
            res = agent_kit.deploy_campaign(target)
            return {"status": "ok", "response": f"☘️ **Kit (Outbound Sales):** {res}", "category": "meta"}
            
        if stripped_cmd.lower().startswith("tell kat") or stripped_cmd.lower().startswith("ask kat"):
            instructions = stripped_cmd.split("kat", 1)[1].strip()
            res = agent_kat.inject_protocol(instructions)
            return {"status": "ok", "response": f"☘️ **Kat (VIP Client Hub):** {res}", "category": "meta"}

        # Original Evolution & Task Commands
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

        # Query the Original Kiemaen Brain
        if ask_kiemaen:
            if inspect.iscoroutinefunction(ask_kiemaen):
                reply, category = await ask_kiemaen(text, image_bytes, doc_text=doc_text, user_key=user_key, is_admin=is_admin, user_id=user["id"])
            else:
                reply, category = ask_kiemaen(text, image_bytes, doc_text=doc_text, user_key=user_key, is_admin=is_admin, user_id=user["id"])
            return {"status": "ok", "response": reply, "category": category}

        return {"status": "ok", "response": "Kiemaen brain module active.", "category": "general"}
    except Exception as e:
        return JSONResponse(status_code=200, content={"status": "error", "message": f"[ERROR] {str(e)}"})

# Direct Enterprise Agent API Endpoints for Dashboard Buttons
@app.post("/api/agent/kim")
async def trigger_kim(data: dict):
    return {"response": agent_kim.execute_trade(data.get("pair", "XAUUSD"), data.get("account", "Vault Markets"))}

@app.post("/api/agent/kit")
async def trigger_kit(data: dict):
    return {"response": agent_kit.deploy_campaign(data.get("target", "Prop Firms"))}

@app.post("/api/agent/kat")
async def trigger_kat(data: dict):
    return {"response": agent_kat.inject_protocol(data.get("instructions", "Update VIP signals"))}

@app.exception_handler(404)
async def custom_404_handler(request, exc):
    return JSONResponse(status_code=404, content={"status": "error", "message": "404: Route not found. The AI mainframe cannot locate this path."})
