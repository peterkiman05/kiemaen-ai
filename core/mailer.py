import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


def send_verification_email(to_email: str, code: str, username: str):
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    sender_email = os.getenv("SENDER_EMAIL", "").strip()
    sender_password = os.getenv("SENDER_PASSWORD", "").replace(" ", "").strip()
    if not sender_email or not sender_password:
        return False, "Email delivery is not configured. Add SENDER_EMAIL and SENDER_PASSWORD."

    msg = MIMEMultipart()
    msg["From"], msg["To"] = sender_email, to_email
    msg["Subject"] = "Kiemaen AI verification code"
    msg.attach(MIMEText(
        f"Hello {username},\n\nYour Kiemaen verification code is {code}. "
        "It expires in 10 minutes. If you did not request this, ignore this email.",
        "plain",
    ))

    try:
        with smtplib.SMTP(smtp_server, smtp_port, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())
        return True, "Verification email sent."
    except smtplib.SMTPAuthenticationError as exc:
        logger.error("Gmail SMTP authentication rejected (SMTP code %s). Check the App Password and 2-Step Verification.", getattr(exc, "smtp_code", "unknown"))
        return False, "Gmail rejected SMTP authentication. Check that the current Gmail App Password is valid."
    except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, TimeoutError, OSError) as exc:
        logger.error("SMTP connection failed (%s): %s", type(exc).__name__, str(exc)[:300])
        return False, "Could not connect to Gmail SMTP. Check SMTP_SERVER and SMTP_PORT."
    except Exception as exc:
        logger.error("SMTP delivery failed (%s): %s", type(exc).__name__, str(exc)[:300])
        return False, "Email delivery failed. Check the Render application logs for the SMTP error category."
