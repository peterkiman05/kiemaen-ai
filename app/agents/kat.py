import json
import os

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

    def auto_evolve(self, feedback_score):
        self.vip_engagement += feedback_score
        if self.vip_engagement > 150:
            self.evolution_level += 1
            self.vip_engagement = 100
            self._save_experience()

    def _save_experience(self):
        with open("data/kat_exp.json", "w") as f:
            json.dump({"level": self.evolution_level, "engagement": self.vip_engagement}, f)

    def receive_task(self, task: str):
        self.active_tasks.append(task)
        return f"Kat: VIP directive logged. [{task}]"

    def ingest_research(self, data: str):
        self.evolution_level += 1
        self._save_experience()
        return f"Kat: VIP sentiment research integrated. Signal fidelity improved."
