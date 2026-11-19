"""Explicit authorization gate for experimental self-evolution features."""
import os
import secrets

# No built-in/default token. Evolution stays disabled until a strong secret is
# explicitly configured in the deployment environment.
AUTHORIZE_EVOLUTION_TOKEN = os.environ.get("EVOLUTION_TOKEN", "").strip()


def verify_evolution_token(token: str) -> bool:
    expected = os.environ.get("EVOLUTION_TOKEN", "").strip()
    supplied = (token or "").strip()
    return bool(expected and supplied) and secrets.compare_digest(supplied, expected)
