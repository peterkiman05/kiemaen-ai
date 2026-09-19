import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_verification_email(to_email: str, code: str, username: str) -> tuple[bool, str]:
    sender = os.getenv("EMAIL_USER")
    app_password = os.getenv("EMAIL_APP_PASSWORD")

    if not sender or not app_password:
        return False, "Email sending is not configured on the server yet."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Your Kiemaen AI Verification Code"
    msg["From"] = sender
    msg["To"] = to_email

    text = f"Hi {username},\n\nYour Kiemaen AI verification code is: {code}\n\nThis code expires in 10 minutes.\n\nIf you didn't request this, you can safely ignore this email."
    html = f"""
    <div style="font-family:sans-serif; padding:20px; background:#0a0e1a; color:#e8eaed;">
      <h2 style="color:#4285f4;">Kiemaen AI</h2>
      <p>Hi {username},</p>
      <p>Your verification code is:</p>
      <div style="font-size:32px; font-weight:bold; letter-spacing:6px; color:#6ea8ff; margin:20px 0;">{code}</div>
      <p style="color:#9aa0a6; font-size:13px;">This code expires in 10 minutes. If you didn't request this, ignore this email.</p>
    </div>
    """

    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender, app_password)
            server.sendmail(sender, to_email, msg.as_string())
        return True, "Verification email sent."
    except Exception as e:
        return False, f"Failed to send email: {e}"
