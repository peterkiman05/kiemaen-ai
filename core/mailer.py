import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_verification_email(to_email: str, code: str, username: str):
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    sender_email = os.getenv("SENDER_EMAIL", "").strip()
    sender_password = os.getenv("SENDER_PASSWORD", "").strip()
    if not sender_email or not sender_password:
        # Never print authentication codes to application logs.
        return False, "Email delivery is not configured. Add SENDER_EMAIL and SENDER_PASSWORD."
    msg = MIMEMultipart()
    msg["From"], msg["To"] = sender_email, to_email
    msg["Subject"] = "Kiemaen AI verification code"
    msg.attach(MIMEText(
        f"Hello {username},\\n\\nYour Kiemaen verification code is {code}. "
        "It expires in 10 minutes. If you did not request this, ignore this email.",
        "plain",
    ))
    try:
        with smtplib.SMTP(smtp_server, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())
        return True, "Verification email sent."
    except Exception:
        return False, "Email delivery failed. Check the SMTP settings."
