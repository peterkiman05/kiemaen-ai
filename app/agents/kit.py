import json
import os

class Kit:
    def __init__(self):
        self.role = "B2B Growth & Outbound Sales Manager"
        self.evolution_level = 1
        self.conversion_rate = 0.0
        self.active_tasks = []
        self._load_experience()

    def _load_experience(self):
        if os.path.exists("data/kit_exp.json"):
            with open("data/kit_exp.json", "r") as f:
                data = json.load(f)
                self.evolution_level = data.get("level", 1)

    def auto_evolve(self, successful_conversions, total_outreach):
        if total_outreach > 0:
            self.conversion_rate = (successful_conversions / total_outreach) * 100
            if self.conversion_rate > 15.0:
                self.evolution_level += 1
                self._save_experience()

    def _save_experience(self):
        with open("data/kit_exp.json", "w") as f:
            json.dump({"level": self.evolution_level, "conversion": self.conversion_rate}, f)

    def receive_task(self, task: str):
        self.active_tasks.append(task)
        return f"Kit: B2B outreach task acquired. [{task}]"

    def ingest_research(self, data: str):
        self.evolution_level += 1
        self._save_experience()
        return f"Kit: New industry lead data processed. Outreach matrices updated."
