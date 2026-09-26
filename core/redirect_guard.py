"""
Redirect safety utility. Not yet wired into any route (Kiemaen currently
has no redirect flows), but ready the moment one is added (e.g., OAuth
callback, email verification links, post-login redirects).
"""
from urllib.parse import urlparse

ALLOWED_DOMAINS = {
    "kiemaen-ai.onrender.com",
}

def validate_redirect_url(url: str) -> tuple[bool, str]:
    """Returns (is_safe, reason). Rejects anything not matching our own domain exactly."""
    if not url:
        return False, "Empty redirect URL."

    if url.startswith("/") and not url.startswith("//"):
        return True, "Relative path, safe."

    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Malformed URL."

    if parsed.scheme not in ("https", "http", ""):
        return False, f"Disallowed scheme: {parsed.scheme}"

    if parsed.netloc and parsed.netloc not in ALLOWED_DOMAINS:
        return False, f"Domain '{parsed.netloc}' is not in the allow-list."

    return True, "Safe."
