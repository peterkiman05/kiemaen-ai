import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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

    def _save_experience(self):
        os.makedirs("data", exist_ok=True)
        with open("data/kit_exp.json", "w") as f:
            json.dump({"level": self.evolution_level, "conversion": self.conversion_rate}, f)

    def deploy_live_campaign(self, smtp_user: str, smtp_pass: str, target_email: str, subject: str, body: str):
        try:
            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = target_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            
            # Defaults to Gmail SMTP for accessibility, easily swapped to Outlook/Titan
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
            server.quit()
            return f"Kit: B2B outreach successfully dispatched to {target_email}."
        except Exception as e:
            return f"Kit Error: Check SMTP credentials. ({str(e)})"
