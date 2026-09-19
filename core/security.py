import time
import os
from collections import defaultdict
from fastapi import Request
from fastapi.responses import JSONResponse

RATE_LIMIT = 60
RATE_WINDOW = 60
request_log = defaultdict(list)

LOCKED_FILES = {"web/index.html", "core/brain.py", "main.py", "tools/coder.py", ".env",
                "core/security.py", "core/auth.py"}

def is_path_safe(path: str) -> bool:
    normalized = os.path.normpath(path).replace("\\", "/").lstrip("/")
    if ".." in normalized.split("/"):
        return False
    if normalized in LOCKED_FILES:
        return False
    return True

async def firewall_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    request_log[client_ip] = [t for t in request_log[client_ip] if now - t < RATE_WINDOW]
    request_log[client_ip].append(now)
    if len(request_log[client_ip]) > RATE_LIMIT:
        return JSONResponse(status_code=429, content={"status": "error", "message": "Too many requests. Please slow down."})
    response = await call_next(request)
    return response
