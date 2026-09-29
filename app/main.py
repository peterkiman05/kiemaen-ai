import httpx
from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from app.config import settings
from app.agents.kit import kit_agent
from app.agents.kat import kat_agent
from app.agents.kim import kim_agent

app = FastAPI(title=settings.PROJECT_NAME)

@app.post("/api/telegram/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    
    if "pre_checkout_query" in data:
        query_id = data["pre_checkout_query"]["id"]
        answer_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/answerPreCheckoutQuery"
        async with httpx.AsyncClient() as client:
            await client.post(answer_url, json={"pre_checkout_query_id": query_id, "ok": True})
        return {"status": "ok"}
        
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        
        if "successful_payment" in data["message"]:
            stars = data["message"]["successful_payment"]["total_amount"]
            success_msg = f"🎉 <b>Payment of {stars} Stars Confirmed!</b>\n\nWelcome to Kiemaen VIP. Here is your invite link:\n👉 https://t.me/+YourPrivateChannelLink"
            background_tasks.add_task(kat_agent.send_reply, chat_id, success_msg)
            return {"status": "ok"}

        raw_text = data["message"].get("text", "")
        # Remove any weird hidden characters Telegram adds
        text = ''.join(char for char in raw_text if char.isprintable()).strip()
        
        if "/prospect" in text:
            company = text.replace("/prospect", "").strip()
            background_tasks.add_task(kit_agent.draft_b2b_proposal, company)
        elif "/ops" in text:
            background_tasks.add_task(kim_agent.run_daily_ops, chat_id)
        elif "/trade" in text:
            pair = text.replace("/trade", "").strip()
            background_tasks.add_task(kim_agent.execute_paper_trade, chat_id, pair)
        elif "/risk" in text:
            args = text.replace("/risk", "").strip()
            background_tasks.add_task(kat_agent.calculate_risk, chat_id, args)
        elif "/vip" in text:
            background_tasks.add_task(kat_agent.send_vip_invoice, chat_id)
        else:
            background_tasks.add_task(kat_agent.process_incoming_message, chat_id, text)

    if "callback_query" in data:
        chat_id = data["callback_query"]["message"]["chat"]["id"]
        callback_data = data["callback_query"]["data"]
        
        if callback_data.startswith("approve_"):
            company = callback_data.replace("approve_", "")
            background_tasks.add_task(kit_agent.dispatch_approved_email, chat_id, company)
        elif callback_data.startswith("escalate_"):
            company = callback_data.replace("escalate_", "")
            background_tasks.add_task(kim_agent.design_enterprise_architecture, chat_id, company)
            
    return {"status": "ok"}

from fastapi import Form
from fastapi.responses import JSONResponse

@app.post("/api/auth/login")
async def login(username: str = Form(...), password: str = Form(...)):
    # Admin Tier (God Mode)
    if username == settings.ADMIN_USERNAME and password == settings.ADMIN_PASSWORD:
        return JSONResponse({"status": "success", "role": "admin", "redirect": "/dashboard_admin"})
    
    # Surface Tier (Client/User Mode)
    # (In the future, this will check your SQLite database for registered users)
    if username.startswith("user_"): 
        return JSONResponse({"status": "success", "role": "user", "redirect": "/dashboard_client"})
        
    return JSONResponse({"status": "error", "message": "Invalid credentials"}, status_code=401)

from fastapi.responses import FileResponse

@app.get("/")
async def serve_home():
    return FileResponse("static/web/index.html")

from pydantic import BaseModel
import sys
import os
import inspect

# Ensure the root directory is accessible to import your old Kiemaen modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class ChatMessage(BaseModel):
    message: str

@app.post("/api/chat/kiemaen")
async def chat_kiemaen(chat: ChatMessage):
    try:
        from core.brain import ask_kiemaen
        
        # Auto-detect if your original function was async or sync
        if inspect.iscoroutinefunction(ask_kiemaen):
            response = await ask_kiemaen(chat.message)
        else:
            response = ask_kiemaen(chat.message)
            
        # Ensure we return a clean string even if the old AI returns a dictionary
        if isinstance(response, dict):
            response = str(response.get("response", response))
            
        return {"status": "success", "response": response}
    except Exception as e:
        return {"status": "error", "response": f"Original Engine Link Error: {str(e)}"}

@app.post("/api/auth/register")
async def register(username: str = Form(...), password: str = Form(...)):
    # In a full production setup, this will insert into your SQLite DB.
    # For now, we simulate a successful user registration.
    if username == settings.ADMIN_USERNAME:
        return JSONResponse({"status": "error", "message": "Username reserved."}, status_code=400)
    
    return JSONResponse({"status": "success", "message": "Registration successful. You may now log in.", "role": "user"})
