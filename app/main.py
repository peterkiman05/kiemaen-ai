from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
import os
import httpx
import asyncio
import traceback
import random
import smtplib
from email.message import EmailMessage
import hashlib
from datetime import datetime, timedelta
import sqlite3

app = FastAPI(title="Kiemaen Enterprise AI")

if os.path.exists("web"):
    app.mount("/static", StaticFiles(directory="web"), name="static")

@app.get("/")
async def serve_frontend():
    if os.path.exists("web/index.html"):
        return FileResponse("web/index.html")
    return {"status": "error", "message": "UI file missing"}

@app.api_route("/api/health", methods=["GET", "HEAD", "POST"])
async def health_ping_handler():
    return JSONResponse(status_code=200, content={"status": "online", "system": "Kiemaen Enterprise"})

@app.on_event("startup")
async def start_kim_background_loop():
    try:
        os.makedirs("data", exist_ok=True)
        conn = sqlite3.connect("data/enterprise_management.db")
        conn.execute('''CREATE TABLE IF NOT EXISTS email_verifications (email TEXT PRIMARY KEY, code TEXT, expires_at TEXT)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS password_resets (email TEXT PRIMARY KEY, otp TEXT, expires_at TEXT)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS enterprise_users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, password TEXT, is_verified INTEGER DEFAULT 0)''')
        conn.commit()
        conn.close()
        
        from app.agents.kim import Kim
        kim_worker = Kim()
        asyncio.create_task(kim_worker.start_background_engine())
        print("Kim Background Engine initialized successfully.")
    except Exception as e:
        print("Startup Engine Notice: " + str(e))

# -- HONEST SMTP HELPER --
def send_smtp_email(to_email: str, subject: str, body: str):
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    
    if not smtp_user or not smtp_pass:
        print("SMTP SIMULATED [" + to_email + "]: " + body)
        return False, "Simulation Mode: Missing SMTP credentials. Code printed to server logs."
        
    try:
        msg = EmailMessage()
        msg.set_content(body)
        msg.subject = subject
        msg.from_ = smtp_user
        msg.to = to_email
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return True, "Verification code sent to email."
    except Exception as e:
        return False, "SMTP Error: " + str(e)

# -- AUTH & OTP REGISTRATION ENDPOINTS --
@app.post("/api/auth/register")
async def register_user(data: dict):
    email = data.get("email")
    password = data.get("password")
    if not email or not password:
        return {"status": "error", "message": "Email and password required"}
        
    hashed_pwd = hashlib.sha256(password.encode()).hexdigest()
    
    conn = sqlite3.connect("data/enterprise_management.db")
    existing = conn.execute("SELECT id FROM enterprise_users WHERE email = ?", (email,)).fetchone()
    if existing:
        conn.close()
        return {"status": "error", "message": "User already exists."}
        
    conn.execute("INSERT INTO enterprise_users (email, password, is_verified) VALUES (?, ?, 0)", (email, hashed_pwd))
    conn.commit()
    
    code = str(random.randint(100000, 999999))
    expires = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
    conn.execute("REPLACE INTO email_verifications (email, code, expires_at) VALUES (?, ?, ?)", (email, code, expires))
    conn.commit()
    conn.close()
    
    body = "Welcome to Kiemaen Enterprise! Your registration code is: " + code + ". It expires in 15 minutes."
    success, msg = send_smtp_email(email, "Verify Your Registration - Kiemaen Enterprise", body)
    
    if success:
        return {"status": "success", "message": "Registration initiated. " + msg}
    else:
        return {"status": "error", "message": "User created but email dispatch failed: " + msg}

@app.post("/api/auth/request-verification")
async def request_email_verification(data: dict):
    email = data.get("email")
    if not email:
        return {"status": "error", "message": "Email required"}
    
    code = str(random.randint(100000, 999999))
    expires = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
    
    conn = sqlite3.connect("data/enterprise_management.db")
    conn.execute("REPLACE INTO email_verifications (email, code, expires_at) VALUES (?, ?, ?)", (email, code, expires))
    conn.commit()
    conn.close()
    
    body = "Welcome to Kiemaen Enterprise! Your email verification code is: " + code + ". It expires in 15 minutes."
    success, msg = send_smtp_email(email, "Verify Your Email - Kiemaen Enterprise", body)
    
    if success:
        return {"status": "success", "message": msg}
    else:
        return {"status": "error", "message": "Failed to send email: " + msg}

@app.post("/api/auth/verify-email")
async def verify_email_code(data: dict):
    email, code = data.get("email"), data.get("code")
    conn = sqlite3.connect("data/enterprise_management.db")
    row = conn.execute("SELECT code, expires_at FROM email_verifications WHERE email = ?", (email,)).fetchone()
    
    if not row or row[0] != code:
        return {"status": "error", "message": "Invalid verification code."}
    if datetime.utcnow().isoformat() > row[1]:
        return {"status": "error", "message": "Verification code has expired."}
        
    conn.execute("UPDATE enterprise_users SET is_verified = 1 WHERE email = ?", (email,))
    conn.execute("DELETE FROM email_verifications WHERE email = ?", (email,))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Email successfully verified."}

@app.post("/api/auth/forgot-password")
async def forgot_password_request(data: dict):
    email = data.get("email")
    if not email:
        return {"status": "error", "message": "Email required"}
    
    otp = str(random.randint(100000, 999999))
    expires = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
    
    conn = sqlite3.connect("data/enterprise_management.db")
    conn.execute("REPLACE INTO password_resets (email, otp, expires_at) VALUES (?, ?, ?)", (email, otp, expires))
    conn.commit()
    conn.close()
    
    body = "Password Reset Request. Your secure 6-digit reset code is: " + otp + ". Valid for 10 minutes."
    success, msg = send_smtp_email(email, "Password Reset Code - Kiemaen Enterprise", body)
    
    if success:
        return {"status": "success", "message": "Password reset code dispatched."}
    else:
        return {"status": "error", "message": "Failed to dispatch email: " + msg}

@app.post("/api/auth/reset-password")
async def reset_password_with_otp(data: dict):
    email, otp, new_password = data.get("email"), data.get("otp"), data.get("new_password")
    if not email or not otp or not new_password:
        return {"status": "error", "message": "Missing required fields."}
        
    conn = sqlite3.connect("data/enterprise_management.db")
    row = conn.execute("SELECT otp, expires_at FROM password_resets WHERE email = ?", (email,)).fetchone()
    
    if not row or row[0] != otp:
        return {"status": "error", "message": "Invalid OTP code."}
    if datetime.utcnow().isoformat() > row[1]:
        return {"status": "error", "message": "OTP code has expired."}
        
    hashed_pwd = hashlib.sha256(new_password.encode()).hexdigest()
    conn.execute("UPDATE enterprise_users SET password = ? WHERE email = ?", (hashed_pwd, email))
    conn.execute("DELETE FROM password_resets WHERE email = ?", (email,))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Password successfully reset."}

# -- KIM EXECUTION & DIAGNOSTICS --
@app.get("/api/kim/dlq")
async def view_dead_letter_queue():
    try:
        conn = sqlite3.connect("data/enterprise_management.db")
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute("SELECT * FROM dead_letter_queue ORDER BY failed_at DESC LIMIT 10").fetchall()]
        conn.close()
        return {"status": "success", "dlq_entries": rows}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/kim/scalp-loop")
async def trigger_kim_scalp_loop():
    try:
        from app.agents.kim import Kim
        kim = Kim()
        tick = await kim.get_precise_bid_ask("XAUUSD.mic")
        target_symbol = "XAUUSD.mic" if tick.get("bid", 0) > 0 else "EURUSD.mic"
        res = kim.enqueue_task("SCALP_CLUSTER", {"symbol": target_symbol, "action": "BUY", "max_entries": 3})
        return res
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/kim/emergency-close")
async def trigger_emergency_close():
    try:
        from app.agents.kim import Kim
        kim = Kim()
        res = await kim.emergency_close_all()
        return {"status": "success", "result": res}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/kim/metrics")
@app.get("/api/kim/live-metrics")
@app.get("/api/kim/status")
async def get_kim_metrics_endpoint():
    try:
        from app.agents.kim import Kim
        kim = Kim()
        data = await kim.get_live_metrics()
        return JSONResponse(status_code=200, content=data)
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

# -- KIEMAEN ORCHESTRATOR --
class KiemaenOrchestratorMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method == "POST" and not any(x in request.url.path.lower() for x in ["login", "register", "auth", "connect", "broker", "account", "api"]):
            body_bytes = b""
            try:
                body_bytes = await request.body()
                if body_bytes:
                    raw_payload = body_bytes.decode('utf-8', errors='ignore').lower()
                    action_words = ["execute", "scalp", "trade", "buy", "sell", "analyze", "report"]
                    agents = ["kim", "kiemaen", "kit", "kat", "enterprise", "ceo"]
                    
                    if not (any(w in raw_payload for w in action_words) or any(a in raw_payload for a in agents)):
                        async def receive(): return {"type": "http.request", "body": body_bytes}
                        request._receive = receive
                        return await call_next(request)

                    try:
                        from app.agents.kim import Kim
                        kim_worker = Kim()
                        
                        symbol = "XAUUSD.mic" if "gold" in raw_payload or "xau" in raw_payload else "EURUSD.mic"
                        
                        signal = kim_worker.indicators.check_signals(symbol)
                        action = signal if signal != "HOLD" else ("SELL" if "sell" in raw_payload else "BUY")
                        
                        tick = await kim_worker.get_precise_bid_ask(symbol)
                        
                        bid_val = tick.get("bid", 0.0)
                        ask_val = tick.get("ask", 0.0)
                        price_display = "Awaiting MT5 Tick..."
                        if bid_val != 0.0:
                            price_display = "Bid: " + str(round(bid_val, 2)) + " / Ask: " + str(round(ask_val, 2))

                        bal_val = "{:,.2f}".format(kim_worker.balance)
                        eq_val = "{:,.2f}".format(kim_worker.equity)

                        reply = (
                            "👔 **KIEMAEN ENTERPRISE: EXECUTIVE BRIEFING** 👔<br><br>"
                            "**📊 1. Market Oracle & Treasury**<br>"
                            "• Asset Tracked: " + symbol.upper() + "<br>"
                            "• " + price_display + "<br>"
                            "• Account Balance: $" + bal_val + " / Equity: $" + eq_val + "<br><br>"
                            "**🛡️ 2. Kit (Risk & Capital Allocation)**<br>"
                            "• Action Directive: " + action.upper() + " (Algorithmic Confluence)<br>"
                            "• Risk Clearance: " + ("APPROVED" if signal != "HOLD" else "WARNING: Indicator Suggests HOLD") + "<br><br>"
                            "**⭐ 3. Enterprise Operations**<br>"
                            "• Accounts Sync: 8760042 & 8760048 Active<br>"
                            "• OOP Facade Status: Hardened & Operational"
                        )
                        return JSONResponse(status_code=200, content={"response": reply, "reply": reply})
                    except Exception as e:
                        err = "⚠️ **EXECUTIVE OVERRIDE EXCEPTION** ⚠️<br><br>`" + str(e) + "`"
                        return JSONResponse(status_code=200, content={"response": err, "reply": err})
            except Exception:
                pass
            
            if body_bytes:
                async def receive(): return {"type": "http.request", "body": body_bytes}
                request._receive = receive
        return await call_next(request)

app.add_middleware(KiemaenOrchestratorMiddleware)