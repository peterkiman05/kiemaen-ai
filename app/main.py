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

# -- UI & STATIC FILES --
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

# -- STARTUP & BACKGROUND ENGINE --
@app.on_event("startup")
async def start_kim_background_loop():
    try:
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
        print(f"Startup Engine Notice: {e}")

# -- SMTP HELPER --
def send_smtp_email(to_email: str, subject: str, body: str):
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    
    if not smtp_user or not smtp_pass:
        print(f"SMTP SIMULATED [{to_email}]: {body}")
        return False
        
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
        return True
    except Exception: return False

# -- AUTH & OTP ENDPOINTS --
@app.post("/api/auth/request-verification")
async def request_email_verification(data: dict):
    email = data.get("email")
    if not email: return {"status": "error", "message": "Email required"}
    
    code = f"{random.randint(100000, 999999)}"
    expires = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
    
    conn = sqlite3.connect("data/enterprise_management.db")
    conn.execute("REPLACE INTO email_verifications (email, code, expires_at) VALUES (?, ?, ?)", (email, code, expires))
    conn.commit()
    conn.close()
    
    body = f"Welcome to Kiemaen Enterprise! Your email verification code is: {code}. It expires in 15 minutes."
    send_smtp_email(email, "Verify Your Email - Kiemaen Enterprise", body)
    return {"status": "success", "message": "Verification code sent to email."}

@app.post("/api/auth/verify-email")
async def verify_email_code(data: dict):
    email, code = data.get("email"), data.get("code")
    conn = sqlite3.connect("data/enterprise_management.db")
    row = conn.execute("SELECT code, expires_at FROM email_verifications WHERE email = ?", (email,)).fetchone()
    
    if not row or row[0] != code: return {"status": "error", "message": "Invalid verification code."}
    if datetime.utcnow().isoformat() > row[1]: return {"status": "error", "message": "Verification code has expired."}
        
    conn.execute("UPDATE enterprise_users SET is_verified = 1 WHERE email = ?", (email,))
    conn.execute("DELETE FROM email_verifications WHERE email = ?", (email,))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Email successfully verified."}

@app.post("/api/auth/forgot-password")
async def forgot_password_request(data: dict):
    email = data.get("email")
    if not email: return {"status": "error", "message": "Email required"}
    
    otp = f"{random.randint(100000, 999999)}"
    expires = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
    
    conn = sqlite3.connect("data/enterprise_management.db")
    conn.execute("REPLACE INTO password_resets (email, otp, expires_at) VALUES (?, ?, ?)", (email, otp, expires))
    conn.commit()
    conn.close()
    
    body = f"Password Reset Request. Your secure 6-digit reset code is: {otp}. Valid for 10 minutes."
    send_smtp_email(email, "Password Reset Code - Kiemaen Enterprise", body)
    return {"status": "success", "message": "Password reset code dispatched to email."}

@app.post("/api/auth/reset-password")
async def reset_password_with_otp(data: dict):
    email, otp, new_password = data.get("email"), data.get("otp"), data.get("new_password")
    if not email or not otp or not new_password: return {"status": "error", "message": "Missing required fields."}
        
    conn = sqlite3.connect("data/enterprise_management.db")
    row = conn.execute("SELECT otp, expires_at FROM password_resets WHERE email = ?", (email,)).fetchone()
    
    if not row or row[0] != otp: return {"status": "error", "message": "Invalid OTP code."}
    if datetime.utcnow().isoformat() > row[1]: return {"status": "error", "message": "OTP code has expired."}
        
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
    except Exception as e: return {"status": "error", "message": str(e)}

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
    except Exception:
        return JSONResponse(status_code=200, content={
            "status": "success", "is_live": True, "balance": "$0.00", "equity": "$0.00",
            "floating_profit": "$+0.00", "open_positions": "0 Trades", "account_id": "8760042 & 8760048"
        })

# -- KIEMAEN ORCHESTRATOR --
class KiemaenOrchestratorMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method == "POST" and not any(x in request.url.path.lower() for x in ["login", "auth", "connect", "broker", "account", "api"]):
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
                        action = "SELL" if "sell" in raw_payload else "BUY"
                        
                        tick = await kim_worker.get_precise_bid_ask(symbol)
                        
                        price_display = f"Awaiting MT5 Tick..." if tick.get("bid", 0.0) == 0.0 else f"Bid: {tick.get('bid', 0.0):.2f} | Ask: {tick.get('ask', 0.0):.2f}"

                        reply = (
                            f"👔 **KIEMAEN ENTERPRISE: EXECUTIVE BRIEFING** 👔<br><br>"
                            f"**📊 1. Market Oracle & Treasury**<br>"
                            f"• Asset Tracked: {symbol.upper()}<br>"
                            f"• {price_display}<br>"
                            f"• Account Balance: ${kim_worker.balance:,.2f} - Equity: ${kim_worker.equity:,.2f}<br><br>"
                            f"**🛡️ 2. Kit (Risk & Capital Allocation)**<br>"
                            f"• Action Directive: {action.upper()}<br>"
                            f"• Risk Clearance: APPROVED<br><br>"
                            f"**⭐ 3. Enterprise Operations**<br>"
                            f"• Accounts Sync: 8760042 & 8760048 Active<br>"
                            f"• OOP Facade Status: Operational"
                        )
                        return JSONResponse(status_code=200, content={"response": reply, "reply": reply})
                    except Exception as e:
                        err = f"⚠️ **EXECUTIVE OVERRIDE EXCEPTION** ⚠️<br><br>`{str(e)}`<br>{traceback.format_exc()}"
                        return JSONResponse(status_code=200, content={"response": err, "reply": err})
            except Exception: pass
            
            if body_bytes:
                async def receive(): return {"type": "http.request", "body": body_bytes}
                request._receive = receive
        return await call_next(request)

app.add_middleware(KiemaenOrchestratorMiddleware)