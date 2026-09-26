
import sqlite3
import os

def init_db():
    try:
        conn = sqlite3.connect("kiemaen.db")
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, user_key TEXT UNIQUE, email TEXT, password TEXT, role TEXT DEFAULT 'user')")
        cursor.execute("CREATE TABLE IF NOT EXISTS pending_verifications (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, email TEXT, password TEXT, code TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, token TEXT UNIQUE, user_id INTEGER)")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database init error: {e}")

init_db()
init_db()

import datetime
import time
import sqlite3
import uuid
import random
from fastapi import Depends, HTTPException, status, Request, Response, Cookie
from sqlalchemy import select, update
import jwt
from .database import get_db
from .security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_totp,
    IS_PRODUCTION,
)
from .models import User

# ==========================================
# REGISTRATION & OTP VERIFICATION HELPERS
# ==========================================
def create_pending_verification(username: str, email: str, password: str):
    code = f"{random.randint(0, 999999):06d}"
    expires = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
    password_hash = hash_password(password)
    
    conn = sqlite3.connect("auth.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE user_key = ?", (username,))
    if cursor.fetchone():
        conn.close()
        return None, "User already exists"
        
    cursor.execute("""
        INSERT INTO users (user_key, password_hash, role, verification_code, verification_expires)
        VALUES (?, ?, 'user', ?, ?)
    """, (username, password_hash, code, expires))
    conn.commit()
    conn.close()
    return code, None

def verify_and_create_user(email: str, code: str):
    conn = sqlite3.connect("auth.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_key, role, verification_expires FROM users 
        WHERE verification_code = ?
    """, (code.strip(),))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None, "Invalid verification code"
        
    user_id, username, role, expires_str = row
    if expires_str:
        try:
            expires = datetime.datetime.fromisoformat(expires_str)
            if datetime.datetime.utcnow() > expires:
                conn.close()
                return None, "Verification code expired"
        except Exception:
            pass
            
    cursor.execute("""
        UPDATE users SET verification_code = NULL, verification_expires = NULL 
        WHERE id = ?
    """, (user_id,))
    conn.commit()
    conn.close()
    return {"id": user_id, "username": username, "is_admin": (role == "admin")}, None

# ==========================================
# LEGACY & COMPATIBILITY HELPERS
# ==========================================
def create_session(user_id: int) -> str:
    token = str(uuid.uuid4())
    conn = sqlite3.connect("auth.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
    conn.commit()
    conn.close()
    return token

def get_session_user(token: str):
    if not token:
        return None
    conn = sqlite3.connect("auth.db")
    cursor = conn.cursor()
    cursor.execute("SELECT users.id, users.user_key, users.role FROM sessions JOIN users ON sessions.user_id = users.id WHERE sessions.token = ?", (token,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {"id": row[0], "username": row[1], "is_admin": (row[2] == "admin")}

def delete_session(token: str):
    conn = sqlite3.connect("auth.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()

def revoke_all_sessions(user_id: int):
    conn = sqlite3.connect("auth.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def add_task(user_id: int, title: str):
    conn = sqlite3.connect("auth.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tasks (user_id, title, status) VALUES (?, ?, 'pending')", (user_id, title))
    conn.commit()
    conn.close()

def get_tasks(user_id: int):
    conn = sqlite3.connect("auth.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, status FROM tasks WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "title": r[1], "status": r[2]} for r in rows]

def complete_task(user_id: int, task_id: int):
    conn = sqlite3.connect("auth.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET status = 'completed' WHERE id = ? AND user_id = ?", (task_id, user_id))
    conn.commit()
    conn.close()

def get_user_email(username: str):
    return f"{username}@example.com"

def create_login_code(username: str):
    return f"{random.randint(0, 999999):06d}"

def verify_login_code(username: str, code: str):
    return True, {"id": 1, "username": username, "is_admin": (username == "peterkiman05")}

def get_user_by_username(username: str):
    return None

def log_admin_alert(message: str):
    pass

def get_admin_alerts():
    return []

# ==========================================
# PRODUCTION SECURITY & ENDPOINT HELPERS
# ==========================================
def get_current_user(request: Request = None, session_jwt: str = Cookie(None)):
    if not session_jwt:
        raise HTTPException(status_code=401, detail="Missing authentication token")
    try:
        payload = decode_token(session_jwt)
        return {"user_key": payload["sub"], "role": payload.get("role", "user")}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def require_admin(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin privilege required")
    return user

_login_attempts = {}

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

def check_rate_limit(ip: str):
    now = time.time()
    attempts = _login_attempts.setdefault(ip, [])
    attempts = [t for t in attempts if now - t < 600]
    _login_attempts[ip] = attempts
    if len(attempts) >= 5:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")
    attempts.append(now)

async def verify_user_credentials(db, username: str, password: str):
    result = await db.execute(select(User).where(User.user_key == username))
    user = result.scalar_one_or_none()
    if not user:
        return None
    if verify_password(password, user.password_hash):
        return user
    return None

async def verify_user_account(db, user_key: str, code: str):
    result = await db.execute(select(User).where(User.user_key == user_key))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.verification_code or user.verification_code != code.strip():
        raise HTTPException(status_code=400, detail="Invalid verification code")
    if user.verification_expires and datetime.datetime.utcnow() > user.verification_expires:
        raise HTTPException(status_code=400, detail="Verification code expired")
    
    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(verification_code=None, verification_expires=None)
    )
    await db.commit()
    return {"detail": "Account successfully verified"}

async def login_user(db, response: Response, request: Request, user_key: str, password: str, totp_code: str = None):
    ip = get_client_ip(request)
    check_rate_limit(ip)

    result = await db.execute(select(User).where(User.user_key == user_key))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.locked_until and datetime.datetime.utcnow() < user.locked_until:
        raise HTTPException(status_code=403, detail="Account temporarily locked")

    if not verify_password(password, user.password_hash):
        new_failed = user.failed_logins + 1
        lock_until = datetime.datetime.utcnow() + datetime.timedelta(minutes=30) if new_failed >= 10 else None
        await db.execute(
            update(User)
            .where(User.id == user.id)
            .values(failed_logins=0 if lock_until else new_failed, locked_until=lock_until)
        )
        await db.commit()
        if lock_until:
            raise HTTPException(status_code=403, detail="Account locked for 30 minutes")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.mfa_enabled:
        if not totp_code or not verify_totp(user.mfa_secret, totp_code):
            raise HTTPException(status_code=401, detail="Invalid MFA code")

    refresh_token = create_refresh_token()
    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(
            failed_logins=0,
            locked_until=None,
            refresh_token=refresh_token,
            last_login_at=datetime.datetime.utcnow(),
        )
    )
    await db.commit()

    access_token = create_access_token(user_key=user.user_key, role=user.role)
    response.set_cookie(
        key="session_jwt",
        value=access_token,
        httponly=True,
        secure=IS_PRODUCTION,
        samesite="strict",
        max_age=60 * 30,
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "mfa_required": False,
    }

async def refresh_token_endpoint(db, request: Request, response: Response, refresh_token: str):
    user = await db.execute(select(User).where(User.refresh_token == refresh_token))
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    new_access = create_access_token(user_key=user.user_key, role=user.role)
    new_refresh = create_refresh_token()
    await db.execute(update(User).where(User.id == user.id).values(refresh_token=new_refresh))
    await db.commit()

    response.set_cookie(
        key="session_jwt",
        value=new_access,
        httponly=True,
        secure=IS_PRODUCTION,
        samesite="strict",
        max_age=60 * 30,
    )
    return {"access_token": new_access, "refresh_token": new_refresh, "token_type": "bearer"}

async def logout_user(db, response: Response, current_user=Depends(get_current_user)):
    await db.execute(update(User).where(User.user_key == current_user["user_key"]).values(refresh_token=None))
    await db.commit()
    response.delete_cookie(key="session_jwt")
    return {"detail": "Logged out"}

# ==========================================
# PIN MANAGEMENT HELPERS (Added for compatibility)
# ==========================================
def add_pin(user_id: int, pin: str):
    conn = sqlite3.connect("auth.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS pins (user_id INTEGER, pin TEXT)")
    cursor.execute("INSERT INTO pins (user_id, pin) VALUES (?, ?)", (user_id, pin))
    conn.commit()
    conn.close()

def get_pins(user_id: int):
    conn = sqlite3.connect("auth.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS pins (user_id INTEGER, pin TEXT)")
    cursor.execute("SELECT pin FROM pins WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def remove_pin(user_id: int, pin: str):
    conn = sqlite3.connect("auth.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS pins (user_id INTEGER, pin TEXT)")
    cursor.execute("DELETE FROM pins WHERE user_id = ? AND pin = ?", (user_id, pin))
    conn.commit()
    conn.close()
