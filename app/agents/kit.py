import json
import os

class Kit:
    def __init__(self):
        self.role = "B2B Growth & Outbound Sales Manager"
        self.evolution_level = 1
        self.conversion_rate = 0.0
        self._load_experience()

    def _load_experience(self):
        if os.path.exists("data/kit_exp.json"):
            with open("data/kit_exp.json", "r") as f:
                data = json.load(f)
                self.evolution_level = data.get("level", 1)

    def auto_evolve(self, successful_conversions, total_outreach):
        # Evolves outreach phrasing based on B2B conversion resonance
        if total_outreach > 0:
            self.conversion_rate = (successful_conversions / total_outreach) * 100
            if self.conversion_rate > 15.0:
                self.evolution_level += 1
                self._save_experience()

    def _save_experience(self):
        with open("data/kit_exp.json", "w") as f:
            json.dump({"level": self.evolution_level, "conversion": self.conversion_rate}, f)

    def deploy_campaign(self, target: str):
        return f"Kit [Level {self.evolution_level}]: Deploying evolved outreach workflow to {target}."
