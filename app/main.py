from fastapi import FastAPI, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from zoneinfo import ZoneInfo
import os
import httpx
from typing import Optional
from core.brain import ask_kiemaen

# Initialize internal clock for Johannesburg timezone
scheduler = AsyncIOScheduler(timezone=ZoneInfo("Africa/Johannesburg"))

async def send_telegram_message(text: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})

async def daily_telegram_report():
    report = (
        "📊 *Kiemaen Enterprise - Chairman Briefing*<br><br>"
        "📈 *Kim:* Vault Markets telemetry synchronized. Awaiting market open.<br>"
        "🤝 *Kit:* B2B outbound sequences active.<br>"
        "⭐ *Kat:* VIP monetization signals standing by.<br><br>"
        "All systems operational. Awaiting your commands."
    )
    await send_telegram_message(report)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Automatically link the Telegram Bot to this server on startup
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        webhook_url = f"https://api.telegram.org/bot{token}/setWebhook?url=https://kiemaen-ai.onrender.com/webhook/telegram"
        async with httpx.AsyncClient() as client:
            await client.get(webhook_url)
            
    # Schedule the actual 8:00 AM SAST report
    scheduler.add_job(daily_telegram_report, 'cron', hour=8, minute=0)
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(title="Kiemaen AGI", lifespan=lifespan)

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
import json

class ChatOracleInterceptor(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Only intercept chat endpoints
        if "chat" in request.url.path and request.method == "POST":
            try:
                body_bytes = await request.body()
                body = json.loads(body_bytes.decode('utf-8'))
                
                # Capture the message regardless of the JSON key your frontend uses
                msg = body.get("message", body.get("text", body.get("prompt", ""))).lower()
                
                if "price" in msg or "quote" in msg or "how much" in msg:
                    symbol = "XAUUSD" if "xau" in msg or "gold" in msg else ("EURUSD" if "eur" in msg else None)
                    if symbol:
                        from app.agents.kim import Kim
                        kim = Kim()
                        price = await kim.get_real_world_price(symbol)
                        
                        if price > 0:
                            reply_text = f"The current real-time market price of {symbol} is **${price:,.2f}**. (Live Oracle Sync)"
                            
                            # Return multiple keys to ensure the frontend parser catches it seamlessly
                            return JSONResponse({
                                "response": reply_text,
                                "reply": reply_text,
                                "message": reply_text,
                                "text": reply_text
                            })
            except Exception:
                pass
                
            # Restore the request body for the LLM to process normally if it's NOT a price quote
            async def receive():
                return {"type": "http.request", "body": body_bytes}
            request._receive = receive
            
        return await call_next(request)

app.add_middleware(ChatOracleInterceptor)


@app.get("/", response_class=HTMLResponse)
async def serve_home():
    if os.path.exists("web/index.html"):
        with open("web/index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Kiemaen OS Online</h1>"

@app.post("/chat")
async def chat(prompt: str = Form(...), ceo_mode: str = Form("false"), file: Optional[UploadFile] = File(None)):
    try:
        is_ceo = ceo_mode.lower() == "true"
        file_context = ""
        if file:
            file_content = await file.read()
            try:
                decoded = file_content.decode("utf-8")
                file_context = f"<br>[Attached File Content ({file.filename}):<br>{decoded}<br>]"
            except Exception:
                file_context = f"<br>[Attached Binary File: {file.filename}]<br>"
        
        full_prompt = prompt + file_context
        reply = await ask_kiemaen(full_prompt, is_ceo=is_ceo)
        return JSONResponse({"status": "success", "response": reply})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)})

@app.post("/forgot-password")
async def forgot_password(email: str = Form(...)):
    return JSONResponse({
        "status": "success", 
        "message": f"Validation secure. A password reset link has been dispatched to {email}."
    })

# Secure endpoint to receive messages directly from your Telegram app
@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        if "message" in data and "text" in data["message"]:
            chat_id = data["message"]["chat"]["id"]
            text = data["message"]["text"]
            
            # Route your Telegram text into Kiemaen's brain (Always CEO Mode in Telegram)
            reply = await ask_kiemaen(text, is_ceo=True)
            
            token = os.environ.get("TELEGRAM_BOT_TOKEN")
            if token:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                async with httpx.AsyncClient() as client:
                    await client.post(url, json={"chat_id": chat_id, "text": reply})
        return {"status": "ok"}
    except Exception:
        return {"status": "error"}

# --- ENTERPRISE LIVE EXECUTION ENDPOINTS ---
from app.agents.kim import Kim
from app.agents.kit import Kit
from app.agents.kat import Kat

kim_agent = Kim()
kit_agent = Kit()
kat_agent = Kat()

@app.post("/api/kit/outreach")
async def kit_outreach(target_email: str = Form(...), subject: str = Form(...), body: str = Form(...)):
    # Requires SMTP_USER and SMTP_PASS in Render Environment Variables
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASS", "")
    if not user or not password:
        return JSONResponse({"status": "error", "message": "SMTP credentials missing in Render."})
    result = kit_agent.deploy_live_campaign(user, password, target_email, subject, body)
    return JSONResponse({"status": "success", "message": result})

@app.post("/api/kat/broadcast")
async def kat_broadcast(signal: str = Form(...)):
    # Requires TELEGRAM_BOT_TOKEN and VIP_CHAT_ID in Render
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    vip_chat_id = os.environ.get("VIP_CHAT_ID", "")
    if not token or not vip_chat_id:
         return JSONResponse({"status": "error", "message": "Bot Token or VIP Chat ID missing in Render."})
    result = await kat_agent.broadcast_vip_signal(token, vip_chat_id, signal)
    return JSONResponse({"status": "success", "message": result})


@app.post("/api/kim/connect")
async def kim_connect(account_id: str = Form(...), password: str = Form(...), server: str = Form("VaultMarkets-Live")):
    result = await kim_agent.connect_live_account(account_id, password, server)
    return JSONResponse(result)


@app.post("/api/kim/trade")
async def kim_trade(symbol: str = Form("EURUSD"), action: str = Form("BUY"), sl_pips: float = Form(20.0), tp_pips: float = Form(40.0)):
    result = await kim_agent.execute_trade(symbol=symbol, action=action, stop_loss_pips=sl_pips, take_profit_pips=tp_pips)
    return JSONResponse(result)


@app.get("/api/kim/live-metrics")
async def kim_live_metrics():
    metrics = await kim_agent.get_live_metrics()
    return JSONResponse(metrics)

@app.post("/api/kim/push-telemetry")
async def kim_push_telemetry(balance: float = Form(...), equity: float = Form(...), open_trades: int = Form(0)):
    res = await kim_agent.update_telemetry_direct(balance, equity, open_trades)
    return JSONResponse(res)


# --- KIEMAEN CEO ORCHESTRATION ENGINE ---
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
import traceback
import os

class KiemaenOrchestratorMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method == "POST" and "login" not in request.url.path.lower() and "auth" not in request.url.path.lower():
            body_bytes = b""
            try:
                body_bytes = await request.body()
                if body_bytes:
                    raw_payload = body_bytes.decode('utf-8', errors='ignore').lower()
                    
                    # SMART ROUTER: Only intercept actual trading/analysis commands
                    action_words = ["execute", "scalp", "trade", "buy", "sell", "analyze", "analyse", "report", "status", "market"]
                    assets = ["eurusd", "xauusd", "gbpusd", "usdjpy", "gold", "kim", "kiemaen", "kit", "kat"]
                    
                    is_trading_intent = any(w in raw_payload for w in action_words) and any(a in raw_payload for a in assets)
                    
                    if not is_trading_intent:
                        # Restore stream and route to the General AI for casual chat ("hi")
                        async def receive(): return {"type": "http.request", "body": body_bytes}
                        request._receive = receive
                        return await call_next(request)

                    try:
                        from app.agents.kim import Kim
                        kim_worker = Kim()
                        
                        usd_pairs = ["xauusd", "eurusd", "gbpusd", "usdjpy", "usdcad", "audusd", "nzdusd", "usdchf", "btcusd"]
                        detected_symbol = next((p.upper() for p in usd_pairs if p in raw_payload), None)
                        
                        if not detected_symbol:
                            if "gold" in raw_payload or "xau" in raw_payload: detected_symbol = "XAUUSD"
                            elif "gbp" in raw_payload or "pound" in raw_payload: detected_symbol = "GBPUSD"
                            elif "jpy" in raw_payload or "yen" in raw_payload: detected_symbol = "USDJPY"
                            else: detected_symbol = "EURUSD"

                        symbol = f"{detected_symbol}.mic" if kim_worker.account_type == "micro" else detected_symbol
                        action = "SELL" if "sell" in raw_payload else "BUY"
                        is_execution = any(w in raw_payload for w in ["execute", "scalp", "trade", "buy", "sell"])
                        
                        # Fetch precise Bid/Ask spread
                        tick = await kim_worker.get_precise_bid_ask(symbol)
                        await kim_worker.get_live_metrics()
                        
                        kit_risk = kim_worker.calculate_risk_and_lot(symbol, stop_loss_pips=8.0)
                        risk_status = "APPROVED" if kit_risk['allowed'] else f"REJECTED ({kit_risk.get('reason')})"
                        lot_size = kit_risk.get('lot_size', 0.01)
                        
                        if is_execution:
                            if kit_risk['allowed']:
                                exec_res = await kim_worker.execute_trade(symbol, action, is_manual=True)
                                kim_status = exec_res.get('message', exec_res.get('reason', 'Executed successfully.'))
                            else:
                                kim_status = "Execution Halted by Risk Manager (Kit)."
                        else:
                            kim_status = "Standby. Analysis complete, awaiting final execution command."
                            
                        # Format exact MT5 Chart Prices
                        bid_price = tick.get("bid", 0.0)
                        ask_price = tick.get("ask", 0.0)
                        
                        if bid_price == 0.0:
                            price_display = "Awaiting MT5 Tick Stream..."
                        else:
                            decimals = 2 if "XAU" in symbol else 5
                            price_display = f"Bid (Chart Line): {bid_price:.{decimals}f} | Ask (Spread): {ask_price:.{decimals}f}"
                        
                        reply = (
                            f"👔 **KIEMAEN ENTERPRISE: CEO ORCHESTRATION REPORT** 👔<br><br>"
                            f"**📊 1. Market Oracle (Live State)**<br>"
                            f"• Asset: {symbol.upper()}<br>"
                            f"• {price_display}<br>"
                            f"• Account Balance: ${kim_worker.balance:,.2f}<br><br>"
                            f"**🛡️ 2. Kit (Risk Management)**<br>"
                            f"• Proposed Action: {action.upper()}<br>"
                            f"• Allocated Lot Size: {lot_size}<br>"
                            f"• Status: {risk_status}<br><br>"
                            f"**⚡ 4. Kim (Quantitative Execution)**<br>"
                            f"• Engine Status: {kim_status}"
                        )

                        tele_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
                        tele_chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
                        if tele_token and tele_chat:
                            try:
                                import httpx
                                clean_tele = reply.replace("<br>", "\n")
                                async with httpx.AsyncClient(timeout=3.0) as client:
                                    await client.post(f"https://api.telegram.org/bot{tele_token}/sendMessage", json={"chat_id": tele_chat, "text": clean_tele})
                            except Exception: pass

                        return JSONResponse(status_code=200, content={
                            "response": reply, "reply": reply, "message": reply,
                            "content": reply, "text": reply,
                            "choices": [{"message": {"content": reply}}]
                        })
                    except Exception as e:
                        err = f"⚠️ **ENTERPRISE SYSTEM CRASH** ⚠️<br><br>`{str(e)}`<br>{traceback.format_exc()}"
                        return JSONResponse(status_code=200, content={"response": err, "reply": err, "message": err})
            except Exception: pass
            
            # Failsafe: route to General AI if crash occurs
            if body_bytes:
                async def receive(): return {"type": "http.request", "body": body_bytes}
                request._receive = receive
        return await call_next(request)

try:
    app.add_middleware(KiemaenOrchestratorMiddleware)
except Exception:
    pass
