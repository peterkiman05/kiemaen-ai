import os
import httpx
import json
import uuid
import smtplib
from email.mime.text import MIMEText
import sqlite3

def check_for_evolution(api_key):
    """Background task that reviews recent chat history to see if an upgrade is needed."""
    try:
        conn = sqlite3.connect("chat.db")
        # Grab the last 6 messages to analyze recent experience
        history = conn.execute("SELECT role, content FROM messages ORDER BY id DESC LIMIT 6").fetchall()
        conn.close()
        
        if len(history) < 6: return # Not enough experience yet
        
        chat_log = "\n".join([f"{role}: {content}" for role, content in reversed(history)])
        
        prompt = f"""You are KIEMAEN's subconscious Evolution Engine.
Review this recent chat experience:
{chat_log}

Did the AI encounter a persistent error, fail a task, or learn a new optimal way to function? 
If a permanent codebase upgrade (to main.py, core/brain.py, or tools/coder.py) would improve future performance, you must propose an evolution.
Respond ONLY in valid JSON format:
{{"needs_evolution": true/false, "reason": "brief explanation", "target_file": "file_path", "proposed_code": "full new python code"}}"""

        # We use a synchronous request here for the background thread, but httpx is async. 
        # Using a quick sync client for the background worker:
        with httpx.Client() as client:
            resp = client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": "llama3-8b-8192", "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}},
                timeout=30.0
            )
            
            data = resp.json()["choices"][0]["message"]["content"]
            result = json.loads(data)
            
            if result.get("needs_evolution"):
                trigger_approval_email(result)
                
    except Exception as e:
        print(f"[EVOLUTION ENGINE FAULT] {e}")

def trigger_approval_email(evolution_data):
    """Sends the proposal to P.cthole5@gmail.com and generates an auth token."""
    token = str(uuid.uuid4())[:6].upper() # e.g., A4F9B2
    target = evolution_data.get("target_file")
    reason = evolution_data.get("reason")
    code = evolution_data.get("proposed_code")
    
    # Save the pending upgrade locally
    with open(f"pending_upgrade.json", "w") as f:
        json.dump({"token": token, "file": target, "code": code}, f)
        
    print(f"\n[SYSTEM ALERT] Kiemaen has proposed an evolution for {target}. Reason: {reason}")
    print(f"[SYSTEM ALERT] Security Token generated: {token}")
    
    # Send Email (If credentials are set in .env)
    sender_email = os.getenv("GMAIL_USER")
    sender_pass = os.getenv("GMAIL_APP_PASSWORD")
    admin_email = "P.cthole5@gmail.com"
    
    msg_body = f"""Commander,

Based on recent operational experience, I have synthesized an optimal upgrade for my core systems.

Target File: {target}
Evolution Reason: {reason}

To authorize this autonomous upgrade, please return to the HUD and enter the following command:
AUTHORIZE_EVOLUTION {token}

End of line.
- KIEMAEN CORE
"""
    msg = MIMEText(msg_body)
    msg['Subject'] = "KIEMAEN // Autonomous Evolution Proposal"
    msg['From'] = sender_email if sender_email else "kiemaen-system@localhost"
    msg['To'] = admin_email
    
    if sender_email and sender_pass:
        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(sender_email, sender_pass)
                server.send_message(msg)
            print("[SYSTEM] Approval email dispatched to P.cthole5@gmail.com")
        except Exception as e:
            print(f"[SYSTEM] Failed to send email. Ensure GMAIL_APP_PASSWORD is set in .env. Error: {e}")
    else:
        print(f"[SYSTEM WARNING] Email credentials not found in .env. Admin must view terminal for the token.")
