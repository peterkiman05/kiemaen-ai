import logging
import httpx
from groq import AsyncGroq
from app.config import settings
from app.database import AsyncSessionLocal
from app.models import LeadModel
from sqlalchemy.future import select

logger = logging.getLogger("kiemaen.kat")
groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)

class KatTelegramService:
    def __init__(self):
        self.telegram_token = settings.TELEGRAM_BOT_TOKEN
        self.api_url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"

    async def log_lead(self, chat_id: int):
        async with AsyncSessionLocal() as session:
            async with session.begin():
                result = await session.execute(select(LeadModel).where(LeadModel.chat_id == chat_id))
                if not result.scalars().first():
                    session.add(LeadModel(chat_id=chat_id))
                    await session.commit()

    async def process_incoming_message(self, chat_id: int, text: str):
        await self.log_lead(chat_id)
        system_prompt = (
            "You are Kat, the Director of Client Relations at Kiemaen. "
            "If a user asks about trading, risk, or lot sizes, offer the /risk calculator. "
            "If they want premium signals or institutional volume alerts, tell them to use the command /vip to purchase a subscription."
        )
        try:
            response = await groq_client.chat.completions.create(
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": text}],
                model="qwen/qwen3.8-27b", temperature=0.4
            )
            reply = response.choices[0].message.content
        except Exception:
            reply = "My system is updating. One moment!"
        await self.send_reply(chat_id, reply)

    async def calculate_risk(self, chat_id: int, args: str):
        await self.log_lead(chat_id)
        try:
            parts = args.split()
            balance, risk_pct, sl_pips = float(parts[0]), float(parts[1]), float(parts[2])
            risk_amount = balance * (risk_pct / 100)
            lot_size = risk_amount / (sl_pips * 10.0)
            reply = f"🧮 <b>Kat's Calculator</b>\nBalance: ${balance:,.2f} | Risk: {risk_pct}%\nStop Loss: {sl_pips} pips\n\n🎯 <b>Recommended Lot Size: {lot_size:.2f} Lots</b>\n\n<i>Ready for premium? Send /vip to upgrade.</i>"
        except Exception:
            reply = "Format: <code>/risk 10000 1 20</code>"
        await self.send_reply(chat_id, reply)

    async def send_vip_invoice(self, chat_id: int):
        invoice_url = f"https://api.telegram.org/bot{self.telegram_token}/sendInvoice"
        payload = {
            "chat_id": chat_id,
            "title": "Kiemaen VIP Signals",
            "description": "1-Month Premium Access to Institutional Desk Alerts.",
            "payload": "vip_1_month_access",
            "currency": "XTR", 
            "prices": [{"label": "1 Month VIP", "amount": 500}] 
        }
        async with httpx.AsyncClient() as client:
            await client.post(invoice_url, json=payload)

    async def send_reply(self, chat_id: int, text: str):
        async with httpx.AsyncClient() as client:
            await client.post(self.api_url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})

kat_agent = KatTelegramService()
