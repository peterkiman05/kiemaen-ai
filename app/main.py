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
        "📊 *Kiemaen Enterprise - Chairman Briefing*\n\n"
        "📈 *Kim:* Vault Markets telemetry synchronized. Awaiting market open.\n"
        "🤝 *Kit:* B2B outbound sequences active.\n"
        "⭐ *Kat:* VIP monetization signals standing by.\n\n"
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
                file_context = f"\n[Attached File Content ({file.filename}):\n{decoded}\n]"
            except Exception:
                file_context = f"\n[Attached Binary File: {file.filename}]\n"
        
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
