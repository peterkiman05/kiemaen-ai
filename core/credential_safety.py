"""Credential hashing helpers for short-lived codes and browser sessions."""
from __future__ import annotations
import hashlib
import hmac
import secrets

_OTP_ITERATIONS = 250_000

def hash_otp_code(code: str) -> str:
    """Store a short-lived OTP as salted PBKDF2, not as plaintext."""
    value = (code or "").strip().encode("utf-8")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", value, salt, _OTP_ITERATIONS)
    return "pbkdf2_sha256$" + str(_OTP_ITERATIONS) + "$" + salt.hex() + "$" + digest.hex()

def verify_otp_code(stored: str | None, supplied: str) -> bool:
    if not stored or not supplied:
        return False
    if stored.startswith("pbkdf2_sha256$"):
        try:
            algorithm, iterations_text, salt_hex, digest_hex = stored.split("$", 3)
            iterations = int(iterations_text)
            if algorithm != "pbkdf2_sha256" or not 100_000 <= iterations <= 500_000:
                return False
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(digest_hex)
            if len(salt) != 16 or len(expected) != 32:
                return False
            actual = hashlib.pbkdf2_hmac("sha256", supplied.strip().encode("utf-8"), salt, iterations)
            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError):
            return False
    # Backward compatibility for existing codes until they expire.
    return hmac.compare_digest(str(stored), supplied.strip())

def hash_session_token(token: str) -> str:
    """Hash a high-entropy browser session token before storing it."""
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()
