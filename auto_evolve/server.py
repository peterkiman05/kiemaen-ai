import os
import asyncio
import secrets
from datetime import datetime
from fastapi import FastAPI, Header, HTTPException
import uvicorn

from auto_evolve.logger_setup import load_config, setup_logger
from auto_evolve.monitor import Monitor, SUGGESTION_QUEUE
from auto_evolve.models import SuggestionStatus

config = load_config()
logger = setup_logger(config=config)
app = FastAPI(title="Kiemaen Auto-Evolve Admin API")
monitor = Monitor(config=config)

def get_token():
    return os.environ.get("AUTO_EVOLVE_TOKEN", "").strip()

def check_auth(x_admin_token):
    expected = get_token()
    supplied = (x_admin_token or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Auto-evolution admin API is disabled: configure AUTO_EVOLVE_TOKEN.")
    if not supplied or not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing admin token.")

@app.on_event("startup")
async def startup_event():
    logger.info("Auto-Evolve server starting up.")
    asyncio.create_task(monitor.run_forever())

@app.get("/admin/health")
async def health(x_admin_token: str = Header(default=None)):
    check_auth(x_admin_token)
    return {"status": "ok", "queue_size": len(SUGGESTION_QUEUE), "time": datetime.utcnow().isoformat()}

@app.get("/admin/list")
async def list_suggestions(x_admin_token: str = Header(default=None)):
    check_auth(x_admin_token)
    return {"suggestions": [s.dict() for s in SUGGESTION_QUEUE.values()]}

@app.post("/admin/approve/{suggestion_id}")
async def approve(suggestion_id: str, x_admin_token: str = Header(default=None)):
    check_auth(x_admin_token)
    s = SUGGESTION_QUEUE.get(suggestion_id)
    if not s:
        raise HTTPException(status_code=404, detail="Suggestion not found.")
    s.status = SuggestionStatus.APPROVED
    s.decided_by = "admin"
    s.decided_at = datetime.utcnow()
    logger.info(f"Suggestion {suggestion_id} APPROVED.")
    logger.info(f"[PLACEHOLDER] No automatic file changes made. Apply manually or via "
                f"core/security.py propose_edit/confirm_edit system: {s.action}")
    return {"result": "approved", "suggestion": s.dict()}

@app.post("/admin/rollback/{suggestion_id}")
async def rollback(suggestion_id: str, x_admin_token: str = Header(default=None)):
    check_auth(x_admin_token)
    s = SUGGESTION_QUEUE.get(suggestion_id)
    if not s:
        raise HTTPException(status_code=404, detail="Suggestion not found.")
    s.status = SuggestionStatus.ROLLED_BACK
    s.decided_by = "admin"
    s.decided_at = datetime.utcnow()
    logger.info(f"Suggestion {suggestion_id} ROLLED BACK.")
    return {"result": "rolled_back", "suggestion": s.dict()}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8081)
