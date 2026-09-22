import sqlite3
import hashlib
import secrets
import os
import random
from datetime import datetime, timedelta

DB_PATH = "memory.db"

def init_auth_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        is_admin INTEGER DEFAULT 0,
        created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER,
        created_at TEXT,
        expires_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS pending_verifications (
        email TEXT PRIMARY KEY,
        username TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        code TEXT NOT NULL,
        created_at TEXT,
        expires_at TEXT
    )""")
    conn.commit()

    # Migration-safe: add email column if upgrading an existing database that predates it
    try:
        c.execute("ALTER TABLE users ADD COLUMN email TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists

    conn.close()

def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()
    return pwd_hash, salt

def create_user(username, password, is_admin=0, email=None):
    init_auth_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    pwd_hash, salt = hash_password(password)
    try:
        c.execute("INSERT INTO users (username, email, password_hash, salt, is_admin, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                  (username, email, pwd_hash, salt, is_admin, datetime.utcnow().isoformat()))
        conn.commit()
        result = True
    except sqlite3.IntegrityError:
        result = False
    conn.close()
    return result

def verify_user(username, password):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, password_hash, salt, is_admin FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    user_id, stored_hash, salt, is_admin = row
    test_hash, _ = hash_password(password, salt)
    if test_hash == stored_hash:
        return {"id": user_id, "username": username, "is_admin": bool(is_admin)}
    return None

def create_session(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    token = secrets.token_hex(32)
    now = datetime.utcnow()
    expires = now + timedelta(hours=24)
    c.execute("INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
              (token, user_id, now.isoformat(), expires.isoformat()))
    conn.commit()
    conn.close()
    return token

def get_session_user(token):
    if not token:
        return None
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""SELECT users.id, users.username, users.is_admin, sessions.expires_at
                 FROM sessions JOIN users ON sessions.user_id = users.id
                 WHERE sessions.token=?""", (token,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    user_id, username, is_admin, expires_at = row
    if datetime.fromisoformat(expires_at) < datetime.utcnow():
        return None
    return {"id": user_id, "username": username, "is_admin": bool(is_admin)}

def delete_session(token):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM sessions WHERE token=?", (token,))
    conn.commit()
    conn.close()

def ensure_admin_exists():
    admin_user = os.getenv("ADMIN_USERNAME", "admin")
    admin_pass = os.getenv("ADMIN_PASSWORD")
    if not admin_pass:
        return
    init_auth_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (admin_user,))
    exists = c.fetchone()
    conn.close()
    if not exists:
        create_user(admin_user, admin_pass, is_admin=1)
        print(f"[Auth] Admin account initialized: {admin_user}")

# ===== EMAIL VERIFICATION SYSTEM =====

def username_taken(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    return row is not None

def email_taken(email):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE email=?", (email,))
    row = c.fetchone()
    conn.close()
    return row is not None

def init_login_security_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS pending_logins (
        username TEXT PRIMARY KEY,
        code TEXT NOT NULL,
        created_at TEXT,
        expires_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS admin_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message TEXT NOT NULL,
        created_at TEXT,
        is_read INTEGER DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS memory_pins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        pinned_text TEXT NOT NULL,
        created_at TEXT
    )""")
    conn.commit()
    conn.close()

def get_user_email(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT email FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    return row[0] if row and row[0] else None

def get_user_by_username(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, username, is_admin FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {"id": row[0], "username": row[1], "is_admin": bool(row[2])}

def create_login_code(username):
    init_login_security_db()
    code = str(random.randint(100000, 999999))
    now = datetime.utcnow()
    expires = now + timedelta(minutes=10)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO pending_logins (username, code, created_at, expires_at) VALUES (?, ?, ?, ?)",
               (username, code, now.isoformat(), expires.isoformat()))
    conn.commit()
    conn.close()
    return code

def verify_login_code(username, code):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT code, expires_at FROM pending_logins WHERE username=?", (username,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False, "No pending login code found. Please log in again."
    stored_code, expires_at = row
    if datetime.fromisoformat(expires_at) < datetime.utcnow():
        c.execute("DELETE FROM pending_logins WHERE username=?", (username,))
        conn.commit()
        conn.close()
        return False, "Login code expired. Please log in again."
    if code.strip() != stored_code:
        conn.close()
        return False, "Incorrect code."
    c.execute("DELETE FROM pending_logins WHERE username=?", (username,))
    conn.commit()
    conn.close()
    return True, "ok"

def log_admin_alert(message):
    init_login_security_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO admin_alerts (message, created_at, is_read) VALUES (?, ?, 0)",
               (message, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def get_admin_alerts():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, message, created_at FROM admin_alerts WHERE is_read=0 ORDER BY id DESC")
    rows = c.fetchall()
    c.execute("UPDATE admin_alerts SET is_read=1 WHERE is_read=0")
    conn.commit()
    conn.close()
    return [{"id": r[0], "message": r[1], "created_at": r[2]} for r in rows]

def add_pin(user_id, text):
    init_login_security_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO memory_pins (user_id, pinned_text, created_at) VALUES (?, ?, ?)",
               (user_id, text, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def get_pins(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, pinned_text FROM memory_pins WHERE user_id=? ORDER BY id", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "text": r[1]} for r in rows]

def remove_pin(user_id, pin_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM memory_pins WHERE id=? AND user_id=?", (pin_id, user_id))
    conn.commit()
    conn.close()

def create_pending_verification(username, email, password):
    """Stores a pending signup and returns a 6-digit code to be emailed to the user."""
    init_auth_db()
    if username_taken(username):
        return None, "Username already taken."
    if email_taken(email):
        return None, "An account with this email already exists."

    pwd_hash, salt = hash_password(password)
    code = str(random.randint(100000, 999999))
    now = datetime.utcnow()
    expires = now + timedelta(minutes=10)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""INSERT OR REPLACE INTO pending_verifications
                 (email, username, password_hash, salt, code, created_at, expires_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
              (email, username, pwd_hash, salt, code, now.isoformat(), expires.isoformat()))
    conn.commit()
    conn.close()
    return code, None

def get_pending_code_admin(email):
    """Admin-only read-only lookup of a pending verification code (does not consume/delete it)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, code, created_at, expires_at FROM pending_verifications WHERE email=?", (email,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    username, code_val, created_at, expires_at = row
    return {"username": username, "code": code_val, "created_at": created_at, "expires_at": expires_at}

def verify_and_create_user(email, code):
    """Checks the code against the pending verification and, if valid, creates the real account."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, password_hash, salt, code, expires_at FROM pending_verifications WHERE email=?", (email,))
    row = c.fetchone()

    if not row:
        conn.close()
        return None, "No pending verification found for this email. Please request a new code."

    username, pwd_hash, salt, stored_code, expires_at = row

    if datetime.fromisoformat(expires_at) < datetime.utcnow():
        c.execute("DELETE FROM pending_verifications WHERE email=?", (email,))
        conn.commit()
        conn.close()
        return None, "Verification code expired. Please request a new one."

    if code.strip() != stored_code:
        conn.close()
        return None, "Incorrect verification code."

    try:
        c.execute("INSERT INTO users (username, email, password_hash, salt, is_admin, created_at) VALUES (?, ?, ?, ?, 0, ?)",
                  (username, email, pwd_hash, salt, datetime.utcnow().isoformat()))
        conn.commit()
        user_id = c.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        return None, "Username or email was just taken. Please try registering again."

    c.execute("DELETE FROM pending_verifications WHERE email=?", (email,))
    conn.commit()
    conn.close()
    return {"id": user_id, "username": username, "is_admin": False}, None
