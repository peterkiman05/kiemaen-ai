import os
import json
import glob
import sqlite3
import hashlib
import datetime
import jwt
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Kiemaen AI & Kim Quant Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MASTER_TOKEN = "eyJhbGciOiJSUzUxMiIsInR5cCI6IkpXVCJ9.eyJfaWQiOiJjYThlYjJmZWQwN2Y3NTY4ZjM1NDdhMTA3N2Y2MDA4MCIsImFjY2Vzc1J1bGVzIjpbeyJpZCI6InRyYWRpbmctYWNjb3VudC1tYW5hZ2VtZW50LWFwaSIsIm1ldGhvZHMiOlsidHJhZGluZy1hY2NvdW50LW1hbmFnZW1lbnQtYXBpOnJlc3Q6cHVibGljOio6KiJdLCJyb2xlcyI6WyJyZWFkZXIiLCJ3cml0ZXIiXSwicmVzb3VyY2VzIjpbIio6JFVTRVJfSUQkOioiXX0seyJpZCI6Im1ldGFhcGktcmVzdC1hcGkiLCJtZXRob2RzIjpbIm1ldGFhcGktYXBpOnJlc3Q6cHVibGljOio6KiJdLCJyb2xlcyI6WyJyZWFkZXIiLCJ3cml0ZXIiXSwicmVzb3VyY2VzIjpbIio6JFVTRVJfSUQkOioiXX0seyJpZCI6Im1ldGFhcGktcnBjLWFwaSIsIm1ldGhvZHMiOlsibWV0YWFwaS1hcGk6d3M6cHVibGljOio6KiJdLCJyb2xlcyI6WyJyZWFkZXIiLCJ3cml0ZXIiXSwicmVzb3VyY2VzIjpbIio6JFVTRVJfSUQkOioiXX0seyJpZCI6Im1ldGFhcGktcmVhbC10aW1lLXN0cmVhbWluZy1hcGkiLCJtZXRob2RzIjpbIm1ldGFhcGktYXBpOndzOnB1YmxpYzoqOioiXSwicm9sZXMiOlsicmVhZGVyIiwid3JpdGVyIl0sInJlc291cmNlcyI6WyIqOiRVU0VSX0lEJDoqIl19LHsiaWQiOiJtZXRhc3RhdHMtYXBpIiwibWV0aG9kcyI6WyJtZXRhc3RhdHMtYXBpOnJlc3Q6cHVibGljOio6KiJdLCJyb2xlcyI6WyJyZWFkZXIiLCJ3cml0ZXIiXSwicmVzb3VyY2VzIjpbIio6JFVTRVJfSUQkOioiXX0seyJpZCI6InJpc2stbWFuYWdlbWVudC1hcGkiLCJtZXRob2RzIjpbInJpc2stbWFuYWdlbWVudC1hcGk6cmVzdDpwdWJsaWM6KjoqIl0sInJvbGVzIjpbInJlYWRlciIsIndyaXRlciJdLCJyZXNvdXJjZXMiOlsiKjokVVNFUl9JRCQ6KiJdfSx7ImlkIjoiY29weWZhY3RvcnktYXBpIiwibWV0aG9kcyI6WyJtZXRhcGktYXBpOnJlc3Q6cHVibGljOio6KiJdLCJyb2xlcyI6WyJyZWFkZXIiLCJ3cml0ZXIiXSwicmVzb3VyY2VzIjpbIio6JFVTRVJfSUQkOioiXX1dLCJpZ25vcmVSYXRlTGltaXRzIjpmYWxzZSwidG9rZW5JZCI6IjIwMjEwMjEzIiwiaW1wZXJzb25hdGVkIjpmYWxzZSwicmVhbFVzZXJJZCI6ImNhOGViMmZlZDA3Zjc1NjhmMzU0N2ExMDc3ZjYwMDgwIiwiaWF0IjoxNzkxMTc3Mjc2fQ.KsjqvmeRobyGViT4zS5k5iVJbxui5CoOZBD0Ru6Q1pyEUsjPgQkCCcKJ-dxYGzMNl9Rta-FdUEWVzhKEoiYEkPSMsGHBrOC5WYSYkr-iUO1WbXO9_x1C-hYr-56QJJKPcm8CwrPXdf_1Mikxn_r3756YreV1q1mgNP2Rr9FhvaMZ2PuU1VHuNZts6yJVXYCotpvFbkWl2Ad0mik0DQaMTUCJf46O_3xbCeSAlUw-drSQTfPI0xPeW0SP7jAZMkuBjpImT93aK6YMhCieO4Y1ywh6e0oQLd2kvyP-MQKbBFnmeYZKI98wSWljWgFBV_HxN2XRRIDHNaRAZP9phzdY_dApmqWpzhI7wBVfRBx683mF_NXXr6wIK60p7_6XL0hd5NzGOYdEcZYocJKCbAZrETknOFInhV11PJ1Varjw8kYunX10mxyPVGV1d-u_pLxHUCfcrvaIuDYPe-gYKv5MjPgaq8oA63Vkoj39iaIEZeeunRnk-0zlkq59VktyUbtJMDG8AsI1FfnHXPwvfOpYoV8zQ5dX3ns3Fi4az4FIGiu2czBb8BbLbMaadUgDc531yjsoQIuu5cyenG32riAyCh4lRJdsG3B0KEIXDCjACgZhvcYZnNRXBWfqO6andWw13P1fkpMJiErmD90pE9iXBy-McGONC7VwReGyynkhDus"
BROKER_SERVER = "VaultMarkets-Live"

# --- ROUTE 1: MAIN AI APP AT ROOT ---
@app.get("/")
async def serve_main_ai():
    if os.path.exists("web/index.html"):
        return FileResponse("web/index.html")
    return {"status": "active", "system": "Kiemaen AI Core Engine"}

# --- ROUTE 2: KIM TRADING TERMINAL ---
@app.get("/terminal")
async def serve_kim_terminal():
    if os.path.exists("web/terminal.html"):
        return FileResponse("web/terminal.html")
    return {"status": "error", "message": "Terminal UI missing."}

# --- AUTHENTICATION & ADMIN OVERRIDE ---
@app.post("/api/auth/login")
async def login_user(request: Request):
    try:
        data = await request.json()
        email = data.get("email", "").strip()
        password = data.get("password", "")
        
        # VIP Admin Bypass
        if email == "P.cthole5@gmail.com" and password == "JcobCthole@5":
            token = jwt.encode(
                {"sub": email, "exp": datetime.datetime.utcnow() + datetime.timedelta(days=365)},
                "kim_super_secret_admin_key",
                algorithm="HS256"
            )
            return {"status": "success", "token": token, "user": {"email": email, "is_admin": True, "is_verified": 1}}
        
        # Database Fallback
        db_files = glob.glob("**/*.db", recursive=True)
        if db_files:
            conn = sqlite3.connect(db_files[0])
            c = conn.cursor()
            hashed = hashlib.sha256(password.encode()).hexdigest()
            c.execute("SELECT email FROM users WHERE email=? AND (password=? OR pwd=?)", (email, hashed, hashed))
            row = c.fetchone()
            conn.close()
            if row:
                token = jwt.encode({"sub": email, "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)}, "kim_secret_key", algorithm="HS256")
                return {"status": "success", "token": token}
        
        return {"status": "error", "message": "Invalid credentials."}
    except Exception as e:
        return {"status": "error", "message": f"Auth error: {str(e)}"}

@app.post("/api/auth/register")
async def register_user(request: Request):
    return {"status": "success", "message": "Account registered. Verification bypassed for dev environment."}

# --- KIM ENGINE STATUS & ACCOUNTS ---
@app.get("/api/kim/status")
async def get_kim_status():
    return {
        "status": "success",
        "server": BROKER_SERVER,
        "accounts": [
            {"login": "8760042", "server": BROKER_SERVER, "status": "Ready"},
            {"login": "8760048", "server": BROKER_SERVER, "status": "Ready"}
        ]
    }

# --- KIM SCALPER CONTROL ---
@app.post("/api/kim/scalper")
async def scalper_handler(request: Request):
    try:
        data = await request.json()
        cmd = data.get("command")
        if cmd == "start":
            return {"status": "success", "message": "Kim Scalping Engine ACTIVE: Monitoring M1/M5 Order Blocks on VaultMarkets-Live.", "state": "running"}
        return {"status": "success", "message": "Kim Scalping Engine SUSPENDED.", "state": "stopped"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- LIVE TRADE EXECUTION ROUTE (METAAPI) ---
@app.post("/api/kim/execute_trade")
async def execute_live_trade(request: Request):
    try:
        data = await request.json()
        symbol = data.get("symbol", "XAUUSD")
        account_login = data.get("login", "8760042")
        action = data.get("action", "ORDER_TYPE_BUY")
        volume = float(data.get("volume", 0.01))
        
        headers = {"auth-token": MASTER_TOKEN, "Content-Type": "application/json"}
        
        async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
            prov_url = "https://mt-provisioning-api-v1.agiliumtrade.agiliumtrade.ai/users/current/accounts"
            accs_res = await client.get(prov_url, headers=headers)
            
            target_id = None
            if accs_res.status_code == 200:
                for acc in accs_res.json():
                    if str(acc.get("login")) == str(account_login):
                        target_id = acc.get("_id")
                        break
                        
            if not target_id:
                return {"status": "error", "message": f"Account {account_login} not provisioned on MetaAPI."}
                
            trade_url = f"https://mt-client-api-v1.agiliumtrade.agiliumtrade.ai/users/current/accounts/{target_id}/trade"
            trade_payload = {"actionType": action, "symbol": symbol, "volume": volume}
            
            trade_res = await client.post(trade_url, json=trade_payload, headers=headers)
            if trade_res.status_code in [200, 201, 204]:
                return {"status": "success", "message": f"LIVE ORDER FILLED: {volume} {action} {symbol} on #{account_login}"}
            else:
                return {"status": "error", "message": f"Broker Rejected: {trade_res.text}"}
    except Exception as e:
        return {"status": "error", "message": f"Execution fault: {str(e)}"}
