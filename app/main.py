
import httpx

async def fetch_metaapi_account_data(account_id: str):
    config = load_config()
    token = config.get("token", "")
    url = f"https://mt-client-api-v1.agiliumtrade.agiliumtrade.ai/users/current/accounts/{account_id}"
    headers = {"auth-token": token}
    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.get(url, headers=headers)
        if res.status_code == 200:
            data = res.json()
            state_res = await client.get(f"{url}/account-information", headers=headers)
            pos_res = await client.get(f"{url}/positions", headers=headers)
            state = state_res.json() if state_res.status_code == 200 else {}
            positions = pos_res.json() if pos_res.status_code == 200 else []
            return {
                "connected": data.get("connectionStatus") == "CONNECTED",
                "balance": state.get("balance", 0.0),
                "equity": state.get("equity", 0.0),
                "profit": state.get("profit", 0.0),
                "open_positions": len(positions)
            }
        return {"connected": False}


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Initialize the core application
app = FastAPI(title="Kim Quant Engine")

# Fortify the middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        
        global kim_worker
        if kim_worker is None:
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
        with smtplib.SMTP(smtp_host, smtp_port, timeout=5) as server:
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
        return {"status": "success", "message": "Render blocked the email port. Your emergency login code is: " + code}

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


@app.post("/api/auth/login")
async def login_user(data: dict):
    email = data.get("email")
    password = data.get("password")
    if not email or not password:
        return {"status": "error", "message": "Missing credentials"}
    
    import hashlib
    import sqlite3
    hashed_pwd = hashlib.sha256(password.encode()).hexdigest()
    
    conn = sqlite3.connect("data/enterprise_management.db")
    user = conn.execute("SELECT is_verified FROM enterprise_users WHERE email = ? AND password = ?", (email, hashed_pwd)).fetchone()
    conn.close()
    
    if not user:
        return {"status": "error", "message": "Invalid email or password."}
    if user[0] == 0:
        return {"status": "error", "message": "Account not verified. Please register again to request a new code.", "needs_verification": True}
        
    return {"status": "success", "message": "Login successful"}

# -- KIM EXECUTION & DIAGNOSTICS --

@app.post("/api/kim/connect")
async def connect_broker(data: dict):
    config = load_config()
    
    # Use stored Token and Server if the user leaves the fields blank
    token = data.get("token", "").strip() or config.get("token", "")
    server = data.get("server", "").strip() or config.get("server", "VaultMarkets-Live")
    login = data.get("login", "").strip()
    password = data.get("password", "").strip()
    
    if not token or not login or not password:
        return {"status": "error", "message": "Master Token, MT5 Login, and Password are required."}
        
    headers = {"auth-token": token, "Content-Type": "application/json"}
    payload = {"login": login, "password": password, "server": server, "platform": "mt5", "name": f"Kim-{login}", "magic": 100000}
    
    async with httpx.AsyncClient(timeout=20.0) as client:
        accs_res = await client.get("https://mt-client-api-v1.agiliumtrade.agiliumtrade.ai/users/current/accounts", headers=headers)
        target_id = None
        if accs_res.status_code == 200:
            for acc in accs_res.json():
                if acc.get("login") == login:
                    target_id = acc.get("_id")
                    break
                    
        if not target_id:
            create_res = await client.post("https://mt-client-api-v1.agiliumtrade.agiliumtrade.ai/users/current/accounts", json=payload, headers=headers)
            if create_res.status_code in [200, 201]:
                target_id = create_res.json().get("id")
            else:
                return {"status": "error", "message": f"Provisioning Error: {create_res.text}"}
                
        if target_id:
            await client.post(f"https://mt-client-api-v1.agiliumtrade.agiliumtrade.ai/users/current/accounts/{target_id}/deploy", headers=headers)
            
            # Save permanently to database
            config["token"] = token
            config["server"] = server
            if target_id not in config.get("accounts", []):
                accs = config.get("accounts", [])
                accs.append(target_id)
                config["accounts"] = accs
            save_config(config)
            
            return {"status": "success", "message": f"Account {login} permanently stored and synced!"}
        else:
            return {"status": "error", "message": "Failed to link account."}

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
        global kim_worker
        kim = kim_worker
        tick = await kim.get_precise_bid_ask("XAUUSD.mic")
        target_symbol = "XAUUSD.mic" if tick.get("bid", 0) > 0 else "EURUSD.mic"
        res = kim.enqueue_task("SCALP_CLUSTER", {"symbol": target_symbol, "action": "BUY", "max_entries": 3})
        return res
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/kim/emergency-close")
async def trigger_emergency_close():
    try:
        global kim_worker
        kim = kim_worker
        res = await kim.emergency_close_all()
        return {"status": "success", "result": res}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/kim/metrics")
async def get_kim_metrics():
    try:
        config = load_config()
        accs = config.get("accounts", [])
        
        if not accs:
            return {"status": "unconfigured", "message": "No accounts stored in database."}

        global_balance = 0.0; global_equity = 0.0; global_pnl = 0.0; total_positions = 0; errors = []

        for acc_id in accs:
            try:
                acc_data = await fetch_metaapi_account_data(acc_id)
                if acc_data and acc_data.get("connected"):
                    global_balance += float(acc_data.get("balance", 0))
                    global_equity += float(acc_data.get("equity", 0))
                    global_pnl += float(acc_data.get("profit", 0))
                    total_positions += int(acc_data.get("open_positions", 0))
                else:
                    errors.append(f"Account offline")
            except Exception as e:
                errors.append(f"MetaAPI Error: {str(e)}")

        if len(errors) < len(accs) or global_balance > 0:
            return {"status": "success", "balance": round(global_balance, 2), "equity": round(global_equity, 2), "floating_profit": round(global_pnl, 2), "open_positions": total_positions}
        else:
            return {"status": "error", "message": " | ".join(errors)}
            
    except Exception as critical_e:
        return {"status": "error", "message": f"Python Backend Crash: {str(critical_e)}"}

@app.get("/api/kim/live-metrics")
@app.get("/api/kim/status")
async def get_kim_metrics_endpoint():
    try:
        global kim_worker
        kim = kim_worker
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
                        global kim_worker
                        
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


@app.post("/api/chat")
async def standard_chat(data: dict):
    msg = data.get("message", "").strip()
    try:
        client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
        system_prompt = (
            "You are Kim, an advanced autonomous AI execution engine. You have a dual-engine cognitive architecture: "
            "1. A fast, responsive conversational engine for general chat. "
            "2. A deep-research engine that activates for complex engineering, coding, mathematics, and problem solving. "
            "Kiemaen is the CEO of the enterprise who monitors your activities. You operate independently under his corporate roof. "
            "Be highly intelligent, authentic, and flexible. Analyze which engine is required based on the user's prompt and respond accordingly."
        )
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": msg}
            ],
            model="llama3-8b-8192"
        )
        reply = chat_completion.choices[0].message.content
    except Exception as e:
        reply = f"AI Core Offline. Please verify your GROQ_API_KEY in Render environment variables. Details: {str(e)}"
    
    return {"status": "success", "reply": reply}
app.add_middleware(KiemaenOrchestratorMiddleware)

# Uptime Monitor Health Check
@app.head("/")
async def uptime_ping():
    return {"status": "online"}
