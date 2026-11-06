import logging
import os

import httpx

logger = logging.getLogger(__name__)


def send_verification_email(to_email: str, code: str, username: str):
    """Send a verification email through the owner's Google Apps Script Gmail relay.

    Render's free web services cannot open outbound SMTP connections. The Apps
    Script web app uses GmailApp under the owner's Google account and is called
    by HTTPS, so no SMTP port or Gmail App Password is needed.
    """
    relay_url = os.getenv("GMAIL_SCRIPT_URL", "").strip()
    relay_secret = os.getenv("GMAIL_SCRIPT_SECRET", "").strip()
    sender_email = os.getenv("SENDER_EMAIL", "").strip()

    if not relay_url or not relay_secret or not sender_email:
        return (
            False,
            "Gmail delivery is not configured. Add GMAIL_SCRIPT_URL, "
            "GMAIL_SCRIPT_SECRET and SENDER_EMAIL to Render."
        )

    payload = {
        "secret": relay_secret,
        "to": to_email,
        "subject": "Kiemaen AI verification code",
        "body": (
            f"Hello {username},\n\n"
            f"Your Kiemaen verification code is {code}. "
            "It expires in 10 minutes. If you did not request this, ignore this email."
        ),
        "senderName": "Kiemaen AI",
        "replyTo": sender_email,
    }

    try:
        response = httpx.post(
            relay_url,
            json=payload,
            timeout=20.0,
            follow_redirects=True,
        )
        response.raise_for_status()
        try:
            result = response.json()
        except ValueError:
            result = {}

        if result.get("ok") is True:
            return True, "Verification email sent."

        reason = str(result.get("error", "Gmail relay rejected the request"))[:200]
        logger.error("Gmail relay rejected verification email: %s", reason)
        return False, "Gmail could not send the verification email. Check the Gmail relay configuration."

    except httpx.HTTPStatusError as exc:
        logger.error(
            "Gmail relay HTTP error (status %s): %s",
            exc.response.status_code,
            exc.response.text[:200],
        )
        return False, "Gmail relay returned an HTTP error. Check the relay deployment and settings."
    except httpx.RequestError as exc:
        logger.error("Gmail relay connection failed (%s): %s", type(exc).__name__, str(exc)[:200])
        return False, "Could not reach the Gmail relay over HTTPS. Check GMAIL_SCRIPT_URL."
    except Exception as exc:
        logger.exception("Unexpected Gmail relay error (%s)", type(exc).__name__)
        return False, "Email delivery failed. Check the Render application logs."
