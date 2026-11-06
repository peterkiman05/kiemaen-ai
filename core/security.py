import os
import uuid
from datetime import datetime, timedelta

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Request

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGO = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
IS_PRODUCTION = bool(os.getenv("RENDER"))


def _jwt_secret():
    if len(JWT_SECRET) < 32:
        raise RuntimeError("JWT_SECRET must be configured with at least 32 characters.")
    return JWT_SECRET


ph = PasswordHasher(time_cost=2, memory_cost=102400, parallelism=8, hash_len=32, salt_len=16)


def hash_password(plain: str) -> str:
    return ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return ph.verify(hashed, plain)
    except VerifyMismatchError:
        return False


def create_access_token(user_key: str, role: str) -> str:
    now = datetime.utcnow()
    payload = {"sub": user_key, "role": role, "iat": int(now.timestamp()),
               "exp": int((now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp())}
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGO)


def create_refresh_token() -> str:
    return str(uuid.uuid4())


def decode_token(token: str) -> dict:
    return jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGO])


def verify_totp(secret: str, token: str) -> bool:
    return bool(secret) and pyotp.TOTP(secret).verify(token, valid_window=1)


LOCKED_FILES = ["main.py", "core/security.py", "core/auth.py", "core/database.py"]


def is_path_safe(path: str) -> bool:
    return bool(path) and ".." not in path and not path.startswith("/")


def is_locked_file(path: str) -> bool:
    return path in LOCKED_FILES


async def firewall_middleware(request: Request, call_next):
    response = await call_next(request)
    return response


def propose_edit(file_path: str, new_code: str):
    if is_locked_file(file_path):
        raise ValueError(f"File {file_path} is locked for security.")
    if not is_path_safe(file_path):
        raise ValueError("Unsafe file path.")
    return {"status": "proposed", "path": file_path}


def confirm_edit(proposal_id: str):
    return {"status": "confirmed"}


def reject_edit(proposal_id: str):
    return {"status": "rejected"}


def rollback_edit(file_path: str):
    return {"status": "rolled_back"}


def validate_python_syntax(code: str) -> bool:
    try:
        compile(code, "<string>", "exec")
        return True
    except SyntaxError:
        return False
