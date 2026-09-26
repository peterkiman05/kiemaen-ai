import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

def send_verification_email(to_email: str, code: str, username: str):
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    sender_email = os.getenv("SENDER_EMAIL", "").strip()
    sender_password = os.getenv("SENDER_PASSWORD", "").strip()

    subject = "Kiemaen AGI - Verification Code"
    body = f"Hello {username},\n\nYour secure verification code is: {code}\n\nThis code will expire in 10 minutes."

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    if not sender_email or not sender_password:
        print(f"\n🔐 [CONSOLE OTP FALLBACK FOR {to_email}]: {code}\n")
        return True, "Code printed to console (No SMTP credentials configured)"

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        print(f"\n📧 [EMAIL SENT SUCCESSFULLY TO {to_email}]\n")
        return True, "Email sent successfully"
    except Exception as e:
        print(f"\n⚠️ [SMTP ERROR]: Failed to send email to {to_email}. Error: {e}\n")
        print(f"🔐 [FALLBACK OTP CODE]: {code}\n")
        return False, str(e)
