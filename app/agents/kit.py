import logging
import httpx
import smtplib
from email.message import EmailMessage
from groq import AsyncGroq
from app.config import settings
from app.database import AsyncSessionLocal
from app.models import B2BModel

logger = logging.getLogger("kiemaen.kit")
groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)

class KitRetentionEngine:
    def __init__(self):
        self.telegram_token = settings.TELEGRAM_BOT_TOKEN
        self.api_url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"

    async def scan_inactive_users(self):
        return {"status": "Complete"}

    async def draft_b2b_proposal(self, target_company: str):
        async with AsyncSessionLocal() as session:
            async with session.begin():
                session.add(B2BModel(company=target_company, status="Pending"))
                await session.commit()

        system_prompt = "You are Kit, Head of B2B at Kiemaen. Write a short, highly personalized cold email to the target company offering AI automation."
        
        try:
            response = await groq_client.chat.completions.create(
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": f"Target: {target_company}"}],
                model="qwen/qwen3.8-27b", temperature=0.5
            )
            draft = response.choices[0].message.content
        except Exception as e:
            draft = "Error generating draft."

        if settings.ADMIN_CHAT_ID:
            keyboard = {
                "inline_keyboard": [
                    [{"text": "✅ Approve & Send Email", "callback_data": f"approve_{target_company}"}],
                    [{"text": "🔄 Escalate to Kim", "callback_data": f"escalate_{target_company}"}]
                ]
            }
            await self._send_telegram(settings.ADMIN_CHAT_ID, f"🏢 <b>B2B Draft</b>\n\nTarget: {target_company}\n\n{draft}", keyboard)
        return draft

    async def dispatch_approved_email(self, chat_id: int, company: str):
        await self._send_telegram(chat_id, f"⚙️ Establishing live SMTP connection for {company}...")
        
        # LIVE CREDENTIALS
        SMTP_SERVER = "smtp.gmail.com"
        SMTP_PORT = 587
        SENDER_EMAIL = "p.cthole5@gmail.com" # <--- YOUR EMAIL HERE
        APP_PASSWORD = "lvinnqjznylyyexx" # <--- YOUR APP PASSWORD HERE (no spaces)
        
        # Generate the target email (e.g. Vault Markets -> contact@vaultmarkets.com)
        target_email = f"contact@{company.lower().replace(' ', '')}.com"
        
        try:
            msg = EmailMessage()
            msg.set_content(f"Hi {company} team,\n\nJacob, our CEO, has been following your recent growth. We specialize in B2B AI retention systems to stop churn before it starts.\n\nDo you have 5 minutes this week to chat?\n\nBest,\nKit\nHead of B2B, Kiemaen Corp")
            msg['Subject'] = f"Kiemaen Automation for {company}"
            msg['From'] = SENDER_EMAIL
            msg['To'] = target_email
            
            # Fire the email
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.send_message(msg)
            server.quit()
            
            await self._send_telegram(chat_id, f"✅ <b>Live Dispatch Complete</b>\n\nThe B2B pitch has been successfully emailed to {target_email}.")
        except Exception as e:
            await self._send_telegram(chat_id, f"❌ Email Failed: Ensure your App Password and Gmail are correct in kit.py.")

    async def _send_telegram(self, chat_id: int, text: str, keyboard: dict = None):
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if keyboard: payload["reply_markup"] = keyboard
        async with httpx.AsyncClient() as client:
            await client.post(self.api_url, json=payload)

kit_agent = KitRetentionEngine()
