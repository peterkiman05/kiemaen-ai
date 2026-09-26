import os
import secrets

AUTHORIZE_EVOLUTION_TOKEN = os.environ.get("EVOLUTION_TOKEN", "kiemaen_evo_secret_2026")

def verify_evolution_token(token: str) -> bool:
    if not token:
        return False
    return secrets.compare_digest(token.strip(), AUTHORIZE_EVOLUTION_TOKEN)
