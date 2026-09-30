import json
import os

class Kim:
    def __init__(self):
        self.role = "Day-to-Day Trading & Quantitative Manager"
        self.broker_name = "Vault Markets"
        self.evolution_level = 1
        self.risk_tolerance = 2.0
        self.active_tasks = []
        self._load_experience()

    def _load_experience(self):
        if os.path.exists("data/kim_exp.json"):
            with open("data/kim_exp.json", "r") as f:
                data = json.load(f)
                self.evolution_level = data.get("level", 1)
                self.risk_tolerance = data.get("risk", 2.0)

    def auto_evolve(self, win_rate, total_trades):
        if win_rate > 60.0 and total_trades > 5:
            self.evolution_level += 1
            self.risk_tolerance = max(0.5, self.risk_tolerance - 0.1)
            self._save_experience()

    def _save_experience(self):
        with open("data/kim_exp.json", "w") as f:
            json.dump({"level": self.evolution_level, "risk": self.risk_tolerance}, f)

    def receive_task(self, task: str):
        self.active_tasks.append(task)
        return f"Kim: Task logged. [{task}]"

    def ingest_research(self, data: str):
        self.evolution_level += 1 # Evolve based on new market data
        self._save_experience()
        return f"Kim: Up-to-date market data ingested. Algorithms adapting."
