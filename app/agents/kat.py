import json
import os
import httpx

class Kat:
    def __init__(self):
        self.role = "VIP Client Relations & Monetization Manager"
        self.evolution_level = 1
        self.vip_engagement = 100
        self.active_tasks = []
        self._load_experience()

    def _load_experience(self):
        if os.path.exists("data/kat_exp.json"):
            with open("data/kat_exp.json", "r") as f:
                data = json.load(f)
                self.evolution_level = data.get("level", 1)

    def _save_experience(self):
        os.makedirs("data", exist_ok=True)
        with open("data/kat_exp.json", "w") as f:
            json.dump({"level": self.evolution_level, "engagement": self.vip_engagement}, f)

    async def broadcast_vip_signal(self, bot_token: str, vip_chat_id: str, signal: str):
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json={"chat_id": vip_chat_id, "text": f"💎 *VIP SIGNAL*\n\n{signal}", "parse_mode": "Markdown"})
            if response.status_code == 200:
                return "Kat: Signal successfully broadcasted to the VIP network."
            return f"Kat Error: Broadcast failed. Verify VIP Chat ID. {response.text}"
