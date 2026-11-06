"""Authentication and account helpers for Kiemaen.

The browser session flow uses the local SQLite database. SQLAlchemy/JWT
helpers remain available for the versioned API routes.
"""
from __future__ import annotations

import datetime
import os
import secrets
import sqlite3
import time
import uuid
from pathlib import Path

import jwt
from fastapi import Cookie, Depends, HTTPException, Request, Response
from sqlalchemy import select, update

from .database import get_db
from .models import User
from .security import (
    IS_PRODUCTION, create_access_token, create_refresh_token, decode_token,
    hash_password, verify_password, verify_totp,
)

DB_PATH = Path(__file__).resolve().parent.parent / "kiemaen.db"


def get_kiemaen_db():
    conn = sqlite3.connect(str(DB_PATH), timeout=20, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_key TEXT UNIQUE NOT NULL,
        email TEXT,
        password_hash TEXT,
        password TEXT,
        role TEXT DEFAULT 'user',
        verification_code TEXT,
        verification_expires TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL,
        expires_at TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        status TEXT DEFAULT 'pending'
    )""")
    cur.execute("CREATE TABLE IF NOT EXISTS pins (user_id INTEGER, pin TEXT)")
    cur.execute("""CREATE TABLE IF NOT EXISTS admin_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    session_columns = {row["name"] for row in cur.execute("PRAGMA table_info(sessions)").fetchall()}
    if "expires_at" not in session_columns:
        cur.execute("ALTER TABLE sessions ADD COLUMN expires_at TEXT")
    existing = {row["name"] for row in cur.execute("PRAGMA table_info(users)").fetchall()}
    for name, definition in (
        ("email", "TEXT"), ("password_hash", "TEXT"), ("password", "TEXT"),
        ("role", "TEXT DEFAULT 'user'"), ("verification_code", "TEXT"),
        ("verification_expires", "TEXT"),
    ):
        if name not in existing:
            cur.execute(f"ALTER TABLE users ADD COLUMN {name} {definition}")
    admin_email = os.getenv("KIEMAEN_ADMIN_EMAIL", "").strip().lower()
    if admin_email:
        cur.execute("UPDATE users SET role='admin' WHERE lower(email)=? AND verification_code IS NULL", (admin_email,))
    conn.commit()
    return conn


def _expiry(value):
    if not value:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(str(value))
        if parsed.tzinfo:
            parsed = parsed.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return parsed
    except (TypeError, ValueError):
        return datetime.datetime.min


def _is_expired(value):
    expiry = _expiry(value)
    return expiry is None or datetime.datetime.utcnow() > expiry


def create_pending_verification(username: str, email: str, password: str):
    username, email = username.strip(), email.strip().lower()
    if len(username) < 3 or len(password) < 10:
        return None, "Use a username of at least 3 characters and a password of at least 10 characters."
    if "@" not in email or len(email) > 254:
        return None, "Enter a valid email address."
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires = (datetime.datetime.utcnow() + datetime.timedelta(minutes=10)).isoformat()
    conn = get_kiemaen_db()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id,user_key,email,verification_code FROM users
               WHERE lower(user_key)=lower(?) OR lower(email)=lower(?)""",
            (username, email),
        )
        matches = cur.fetchall()
        if matches:
            # A previous registration may have sent a code but never been verified.
            # Reuse that pending account and issue a fresh code instead of blocking
            # the user as though the account were fully registered.
            if len(matches) != 1:
                return None, "The username and email are associated with different accounts. Contact support."
            existing = matches[0]
            same_identity = (
                existing["user_key"].lower() == username.lower()
                and (existing["email"] or "").lower() == email.lower()
            )
            if not same_identity:
                return None, "That username or email is already registered."
            if existing["verification_code"] is None:
                return None, "That username or email is already registered."
            cur.execute(
                """UPDATE users SET password_hash=?,verification_code=?,verification_expires=?
                   WHERE id=?""",
                (hash_password(password), code, expires, existing["id"]),
            )
        else:
            admin_email = os.getenv("KIEMAEN_ADMIN_EMAIL", "").strip().lower()
            role = "admin" if admin_email and email == admin_email else "user"
            cur.execute(
                """INSERT INTO users (user_key,email,password_hash,role,verification_code,verification_expires)
                   VALUES (?,?,?,?,?,?)""",
                (username, email, hash_password(password), role, code, expires),
            )
        conn.commit()
        return code, None
    finally:
        conn.close()


def verify_and_create_user(email: str, code: str):
    conn = get_kiemaen_db()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id,user_key,role,verification_expires FROM users
               WHERE lower(email)=lower(?) AND verification_code=?""",
            (email.strip(), code.strip()),
        )
        row = cur.fetchone()
        if not row:
            return None, "Invalid email or verification code."
        if _is_expired(row["verification_expires"]):
            cur.execute("DELETE FROM users WHERE id=?", (row["id"],))
            conn.commit()
            return None, "Verification code expired. Please register again."
        cur.execute("UPDATE users SET verification_code=NULL,verification_expires=NULL WHERE id=?", (row["id"],))
        conn.commit()
        return {"id": row["id"], "username": row["user_key"], "is_admin": row["role"] == "admin"}, None
    finally:
        conn.close()


def verify_user_credentials(username: str, password: str):
    conn = get_kiemaen_db()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id,user_key,password_hash,role,verification_code
               FROM users WHERE lower(user_key)=lower(?) OR lower(email)=lower(?) LIMIT 1""",
            (username.strip(), username.strip()),
        )
        row = cur.fetchone()
        if not row or row["verification_code"] or not row["password_hash"]:
            return None
        try:
            valid = verify_password(password, row["password_hash"])
        except Exception:
            valid = False
        if not valid:
            return None
        return {"id": row["id"], "username": row["user_key"], "is_admin": row["role"] == "admin"}
    finally:
        conn.close()


def get_user_email(username: str):
    conn = get_kiemaen_db()
    try:
        row = conn.execute(
            "SELECT email FROM users WHERE lower(user_key)=lower(?) OR lower(email)=lower(?) LIMIT 1",
            (username.strip(), username.strip()),
        ).fetchone()
        return row["email"] if row and row["email"] else None
    finally:
        conn.close()


def create_login_code(username: str):
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires = (datetime.datetime.utcnow() + datetime.timedelta(minutes=10)).isoformat()
    conn = get_kiemaen_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET verification_code=?,verification_expires=? WHERE lower(user_key)=lower(?) OR lower(email)=lower(?)",
            (code, expires, username.strip(), username.strip()),
        )
        conn.commit()
        return code if cur.rowcount else None
    finally:
        conn.close()


def verify_login_code(username: str, code: str):
    conn = get_kiemaen_db()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id,user_key,role,verification_expires FROM users
               WHERE (lower(user_key)=lower(?) OR lower(email)=lower(?)) AND verification_code=?""",
            (username.strip(), username.strip(), code.strip()),
        )
        row = cur.fetchone()
        if not row:
            return False, "Invalid login code."
        if _is_expired(row["verification_expires"]):
            cur.execute("UPDATE users SET verification_code=NULL,verification_expires=NULL WHERE id=?", (row["id"],))
            conn.commit()
            return False, "Login code expired. Request a new one."
        cur.execute("UPDATE users SET verification_code=NULL,verification_expires=NULL WHERE id=?", (row["id"],))
        conn.commit()
        return True, {"id": row["id"], "username": row["user_key"], "is_admin": row["role"] == "admin"}
    finally:
        conn.close()


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    conn = get_kiemaen_db()
    try:
        expiry = (datetime.datetime.utcnow() + datetime.timedelta(days=1)).isoformat()
        conn.execute("INSERT INTO sessions (token,user_id,expires_at) VALUES (?,?,?)", (token, user_id, expiry))
        conn.commit()
        return token
    finally:
        conn.close()


def get_session_user(token: str):
    if not token:
        return None
    conn = get_kiemaen_db()
    try:
        row = conn.execute(
            """SELECT u.id,u.user_key,u.role FROM sessions s
               JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires_at>?""",
            (token, datetime.datetime.utcnow().isoformat()),
        ).fetchone()
        if not row:
            return None
        return {"id": row["id"], "username": row["user_key"], "is_admin": row["role"] == "admin"}
    finally:
        conn.close()


def delete_session(token: str):
    if not token:
        return
    conn = get_kiemaen_db()
    try:
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))
        conn.commit()
    finally:
        conn.close()


def revoke_all_sessions(user_id: int):
    conn = get_kiemaen_db()
    try:
        conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        conn.commit()
    finally:
        conn.close()


def get_user_by_username(username: str):
    conn = get_kiemaen_db()
    try:
        row = conn.execute(
            "SELECT id,user_key,email,role FROM users WHERE lower(user_key)=lower(?)",
            (username.strip(),),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def add_task(user_id: int, title: str):
    conn = get_kiemaen_db()
    try:
        conn.execute("INSERT INTO tasks (user_id,title,status) VALUES (?,?,'pending')", (user_id, title))
        conn.commit()
    finally:
        conn.close()


def get_tasks(user_id: int):
    conn = get_kiemaen_db()
    try:
        rows = conn.execute("SELECT id,title,status FROM tasks WHERE user_id=? ORDER BY id DESC", (user_id,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def complete_task(user_id: int, task_id: int):
    conn = get_kiemaen_db()
    try:
        cur = conn.execute("UPDATE tasks SET status='completed' WHERE id=? AND user_id=?", (task_id, user_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def log_admin_alert(message: str):
    conn = get_kiemaen_db()
    try:
        conn.execute("INSERT INTO admin_alerts(message,created_at) VALUES (?,?)", (message, datetime.datetime.utcnow().isoformat()))
        conn.commit()
    finally:
        conn.close()


def get_admin_alerts():
    conn = get_kiemaen_db()
    try:
        return [dict(row) for row in conn.execute("SELECT * FROM admin_alerts ORDER BY id DESC LIMIT 100").fetchall()]
    finally:
        conn.close()


def add_pin(user_id: int, pin: str):
    conn = get_kiemaen_db()
    try:
        conn.execute("INSERT INTO pins(user_id,pin) VALUES (?,?)", (user_id, pin))
        conn.commit()
    finally:
        conn.close()


def get_pins(user_id: int):
    conn = get_kiemaen_db()
    try:
        return [r["pin"] for r in conn.execute("SELECT pin FROM pins WHERE user_id=?", (user_id,)).fetchall()]
    finally:
        conn.close()


def remove_pin(user_id: int, pin: str):
    conn = get_kiemaen_db()
    try:
        conn.execute("DELETE FROM pins WHERE user_id=? AND pin=?", (user_id, pin))
        conn.commit()
    finally:
        conn.close()


# SQLAlchemy/JWT API authentication helpers.
_login_attempts = {}


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def check_rate_limit(ip: str):
    now = time.time()
    attempts = [t for t in _login_attempts.get(ip, []) if now - t < 600]
    if len(attempts) >= 5:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")
    attempts.append(now)
    _login_attempts[ip] = attempts


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


async def verify_user_account(db, user_key: str, code: str):
    result = await db.execute(select(User).where(User.user_key == user_key))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.verification_code or not secrets.compare_digest(user.verification_code, code.strip()):
        raise HTTPException(status_code=400, detail="Invalid verification code")
    if not user.verification_expires or datetime.datetime.utcnow() > user.verification_expires:
        raise HTTPException(status_code=400, detail="Verification code expired")
    await db.execute(update(User).where(User.id == user.id).values(verification_code=None, verification_expires=None))
    await db.commit()
    return {"detail": "Account successfully verified"}


async def login_user(db, response: Response, request: Request, user_key: str, password: str, totp_code: str = None):
    check_rate_limit(get_client_ip(request))
    result = await db.execute(select(User).where(User.user_key == user_key))
    user = result.scalar_one_or_none()
    if not user or (user.verification_code is not None):
        raise HTTPException(status_code=401, detail="Invalid credentials or unverified account")
    if user.locked_until and datetime.datetime.utcnow() < user.locked_until:
        raise HTTPException(status_code=403, detail="Account temporarily locked")
    try:
        valid = verify_password(password, user.password_hash)
    except Exception:
        valid = False
    if not valid:
        new_failed = (user.failed_logins or 0) + 1
        lock_until = datetime.datetime.utcnow() + datetime.timedelta(minutes=30) if new_failed >= 10 else None
        await db.execute(update(User).where(User.id == user.id).values(failed_logins=0 if lock_until else new_failed, locked_until=lock_until))
        await db.commit()
        raise HTTPException(status_code=403 if lock_until else 401, detail="Account temporarily locked" if lock_until else "Invalid credentials")
    if user.mfa_enabled and (not totp_code or not verify_totp(user.mfa_secret, totp_code)):
        raise HTTPException(status_code=401, detail="Invalid MFA code")
    refresh_token = create_refresh_token()
    await db.execute(update(User).where(User.id == user.id).values(
        failed_logins=0, locked_until=None, refresh_token=refresh_token,
        last_login_at=datetime.datetime.utcnow()))
    await db.commit()
    access_token = create_access_token(user_key=user.user_key, role=user.role)
    response.set_cookie("session_jwt", access_token, httponly=True, secure=IS_PRODUCTION,
                        samesite="strict", max_age=1800, path="/")
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer", "mfa_required": False}


async def refresh_token_endpoint(db, request: Request, response: Response, refresh_token: str):
    result = await db.execute(select(User).where(User.refresh_token == refresh_token))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    new_access, new_refresh = create_access_token(user_key=user.user_key, role=user.role), create_refresh_token()
    await db.execute(update(User).where(User.id == user.id).values(refresh_token=new_refresh))
    await db.commit()
    response.set_cookie("session_jwt", new_access, httponly=True, secure=IS_PRODUCTION,
                        samesite="strict", max_age=1800, path="/")
    return {"access_token": new_access, "refresh_token": new_refresh, "token_type": "bearer"}


async def logout_user(db, response: Response, current_user=Depends(get_current_user)):
    await db.execute(update(User).where(User.user_key == current_user["user_key"]).values(refresh_token=None))
    await db.commit()
    response.delete_cookie("session_jwt", path="/")
    return {"detail": "Logged out"}
