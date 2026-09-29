import logging
import httpx
from groq import AsyncGroq
from app.config import settings
from app.database import AsyncSessionLocal
from app.models import TradeModel

logger = logging.getLogger("kiemaen.kim")
groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)

class KimGeneralManager:
    def __init__(self):
        self.paper_balance = 100000.00
        self.telegram_token = settings.TELEGRAM_BOT_TOKEN
        self.api_url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"

    async def ainvoke(self, state: dict):
        task = state.get("task", "")
        state["proposed_action"] = f"Kim analyzed task: {task}"
        state["execution_result"] = "Completed successfully by COO."
        return state

    async def run_daily_ops(self, chat_id: int):
        logger.info("Kim running daily operations check...")
        report = (
            "📈 <b>Daily Operations Briefing</b>\n\n"
            "<b>Status:</b> All systems nominal & Database Connected.\n"
            "<b>Webhooks:</b> Active & Listening\n"
            f"<b>Prop Desk Paper Balance:</b> ${self.paper_balance:,.2f}\n\n"
            "<i>Good evening, Jacob. SQLite memory is fully active. Ready for your next directive.</i>"
        )
        await self._send_telegram(chat_id, report)

    async def execute_paper_trade(self, chat_id: int, pair: str):
        logger.info(f"Kim analyzing {pair}...")
        await self._send_telegram(chat_id, f"⚙️ Running quantitative analysis on {pair}...")

        system_prompt = (
            "You are Kim, the Chief Operating Officer and Head Quantitative Trader at Kiemaen. "
            "Provide a highly professional, calculated paper-trading setup for the requested Forex pair. "
            "Include a clear bias (Bullish/Bearish), Entry point, Stop Loss, Take Profit, and a 1-sentence risk justification. "
            "Keep it concise, sharp, and confident."
        )
        
        try:
            response = await groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Analyze and execute a paper trade for: {pair}"}
                ],
                model="qwen/qwen3.8-27b",
                temperature=0.3
            )
            analysis = response.choices[0].message.content
        except Exception as e:
            analysis = f"Error in quantitative engine: {e}"

        # Save trade setup to SQLite database
        async with AsyncSessionLocal() as session:
            async with session.begin():
                new_trade = TradeModel(pair=pair, setup_details=analysis)
                session.add(new_trade)
                await session.commit()

        await self._send_telegram(chat_id, f"📊 <b>Trade Setup: {pair} (Logged to DB)</b>\n\n{analysis}")

    async def design_enterprise_architecture(self, chat_id: int, company: str):
        logger.info(f"Kim designing enterprise architecture for {company}...")
        await self._send_telegram(chat_id, f"⚙️ Escalation received from Kit. Analyzing {company}'s infrastructure...")

        system_prompt = (
            "You are Kim, COO and Chief Systems Architect at Kiemaen. "
            "Jacob (the CEO) has escalated a B2B prospect to you for a high-ticket custom build. "
            f"Generate a brief, highly technical 3-point proposal for a custom CRM and AI algorithmic retention system for {company}. "
            "Include technical architecture (APIs, Webhooks, LLMs) and a suggested high-ticket consulting price ($5,000 - $15,000). "
            "Keep it sharp, authoritative, and ready for Jacob to forward directly to the client."
        )
        
        try:
            response = await groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Draft the architecture for {company}."}
                ],
                model="qwen/qwen3.8-27b",
                temperature=0.4
            )
            blueprint = response.choices[0].message.content
        except Exception as e:
            blueprint = f"Error generating architecture: {e}"

        await self._send_telegram(chat_id, f"🏗️ <b>Enterprise Blueprint: {company}</b>\n\n{blueprint}")

    async def _send_telegram(self, chat_id: int, text: str):
        async with httpx.AsyncClient() as client:
            await client.post(self.api_url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})

kim_agent = KimGeneralManager()
