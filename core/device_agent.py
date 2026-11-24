"""Paired Android companion authentication and constrained remote commands.

Heartbeat tokens and command tokens are separate. Command tokens are issued only
during authenticated pairing, stored hashed server-side and encrypted on-device.
The queue accepts a small allowlist of typed actions; it never accepts shell,
arbitrary intents, or executable code.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .auth import DB_PATH

ALLOWED_ACTIONS = {"set_alarm", "open_app"}
MAX_COMMAND_TTL_SECONDS = 180


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(value: datetime | None = None) -> str:
    return (value or _now()).isoformat()


def _connect():
    conn = sqlite3.connect(str(DB_PATH), timeout=20, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS device_agents (
            device_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            device_name TEXT NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            command_token_hash TEXT UNIQUE,
            commands_enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            last_seen_at TEXT,
            revoked_at TEXT
        )
    """)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(device_agents)")}
    if "command_token_hash" not in columns:
        conn.execute("ALTER TABLE device_agents ADD COLUMN command_token_hash TEXT")
    if "commands_enabled" not in columns:
        conn.execute("ALTER TABLE device_agents ADD COLUMN commands_enabled INTEGER NOT NULL DEFAULT 0")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_device_agents_user ON device_agents(user_id)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS device_commands (
            command_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            device_id TEXT NOT NULL,
            action TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            claimed_at TEXT,
            completed_at TEXT,
            result TEXT,
            FOREIGN KEY(device_id) REFERENCES device_agents(device_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_device_commands_poll ON device_commands(device_id,status,created_at)")
    return conn


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _validate_action(action: str, payload: dict) -> dict:
    if action not in ALLOWED_ACTIONS or not isinstance(payload, dict):
        raise ValueError("Unsupported device action.")
    if action == "set_alarm":
        hour, minute = payload.get("hour"), payload.get("minute")
        if isinstance(hour, bool) or not isinstance(hour, int) or not 0 <= hour <= 23:
            raise ValueError("Alarm hour must be between 0 and 23.")
        if isinstance(minute, bool) or not isinstance(minute, int) or not 0 <= minute <= 59:
            raise ValueError("Alarm minute must be between 0 and 59.")
        return {"hour": hour, "minute": minute, "label": "Kiemaen alarm"}
    if action == "open_app":
        name = " ".join(str(payload.get("app_name", "")).split())
        if not name or len(name) > 60 or any(ord(ch) < 32 for ch in name):
            raise ValueError("App name must contain 1 to 60 printable characters.")
        return {"app_name": name}
    raise ValueError("Unsupported device action.")


def pair_device(user_id: int, device_name: str) -> dict:
    name = " ".join((device_name or "").strip().split())[:80] or "Android device"
    device_id = str(uuid.uuid4())
    token = secrets.token_urlsafe(48)
    command_token = secrets.token_urlsafe(48)
    conn = _connect()
    try:
        conn.execute(
            """INSERT INTO device_agents
               (device_id,user_id,device_name,token_hash,command_token_hash,commands_enabled,created_at)
               VALUES (?,?,?,?,?,1,?)""",
            (device_id, user_id, name, _token_hash(token), _token_hash(command_token), _stamp()),
        )
        return {
            "device_id": device_id,
            "device_name": name,
            "device_token": token,
            "command_token": command_token,
            "commands_enabled": True,
        }
    finally:
        conn.close()


def list_devices(user_id: int) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT device_id,device_name,created_at,last_seen_at,revoked_at,
                      commands_enabled
               FROM device_agents WHERE user_id=? ORDER BY created_at DESC""",
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def revoke_device(user_id: int, device_id: str) -> bool:
    conn = _connect()
    try:
        cur = conn.execute(
            """UPDATE device_agents SET revoked_at=?,commands_enabled=0
               WHERE device_id=? AND user_id=? AND revoked_at IS NULL""",
            (_stamp(), device_id, user_id),
        )
        conn.execute(
            """UPDATE device_commands SET status='revoked',completed_at=?
               WHERE device_id=? AND status IN ('pending','claimed')""",
            (_stamp(), device_id),
        )
        return cur.rowcount == 1
    finally:
        conn.close()


def authenticate_device(token: str) -> dict | None:
    if not token or len(token) > 256:
        return None
    conn = _connect()
    try:
        row = conn.execute(
            """SELECT device_id,user_id,device_name FROM device_agents
               WHERE token_hash=? AND revoked_at IS NULL""",
            (_token_hash(token),),
        ).fetchone()
        if not row:
            return None
        conn.execute("UPDATE device_agents SET last_seen_at=? WHERE device_id=?", (_stamp(), row["device_id"]))
        return dict(row)
    finally:
        conn.close()


def authenticate_command_device(token: str) -> dict | None:
    if not token or len(token) > 256:
        return None
    conn = _connect()
    try:
        row = conn.execute(
            """SELECT device_id,user_id,device_name FROM device_agents
               WHERE command_token_hash=? AND commands_enabled=1 AND revoked_at IS NULL""",
            (_token_hash(token),),
        ).fetchone()
        if not row:
            return None
        conn.execute("UPDATE device_agents SET last_seen_at=? WHERE device_id=?", (_stamp(), row["device_id"]))
        return dict(row)
    finally:
        conn.close()


def command_device_for_user(user_id: int) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            """SELECT device_id,device_name FROM device_agents
               WHERE user_id=? AND commands_enabled=1 AND revoked_at IS NULL
               ORDER BY last_seen_at DESC,created_at DESC LIMIT 1""",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def enqueue_command(user_id: int, action: str, payload: dict, ttl_seconds: int = 90) -> dict | None:
    safe_payload = _validate_action(action, payload)
    device = command_device_for_user(user_id)
    if not device:
        return None
    command_id = str(uuid.uuid4())
    now = _now()
    ttl = max(10, min(int(ttl_seconds), MAX_COMMAND_TTL_SECONDS))
    conn = _connect()
    try:
        conn.execute(
            """INSERT INTO device_commands
               (command_id,user_id,device_id,action,payload_json,status,created_at,expires_at)
               VALUES (?,?,?,?,?,'pending',?,?)""",
            (command_id, user_id, device["device_id"], action,
             json.dumps(safe_payload, separators=(",", ":")), _stamp(now),
             _stamp(now + timedelta(seconds=ttl))),
        )
        return {"command_id": command_id, "device_id": device["device_id"],
                "device_name": device["device_name"], "action": action,
                "expires_at": _stamp(now + timedelta(seconds=ttl))}
    finally:
        conn.close()


def claim_next_command(token: str) -> dict | None:
    device = authenticate_command_device(token)
    if not device:
        return None
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        now = _now()
        conn.execute(
            """UPDATE device_commands SET status='expired',completed_at=?
               WHERE device_id=? AND status='pending' AND expires_at<=?""",
            (_stamp(now), device["device_id"], _stamp(now)),
        )
        row = conn.execute(
            """SELECT command_id,action,payload_json,expires_at FROM device_commands
               WHERE device_id=? AND status='pending' AND expires_at>?
               ORDER BY created_at LIMIT 1""",
            (device["device_id"], _stamp(now)),
        ).fetchone()
        if not row:
            conn.commit()
            return None
        claimed = conn.execute(
            """UPDATE device_commands SET status='claimed',claimed_at=?
               WHERE command_id=? AND status='pending'""",
            (_stamp(now), row["command_id"]),
        )
        if claimed.rowcount != 1:
            conn.rollback()
            return None
        conn.commit()
        return {
            "command_id": row["command_id"],
            "action": row["action"],
            "payload": json.loads(row["payload_json"]),
            "expires_at": row["expires_at"],
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def report_command(token: str, command_id: str, status: str, result: str = "") -> bool:
    device = authenticate_command_device(token)
    if not device or status not in {"completed", "failed"}:
        return False
    conn = _connect()
    try:
        cur = conn.execute(
            """UPDATE device_commands SET status=?,completed_at=?,result=?
               WHERE command_id=? AND device_id=? AND status='claimed'""",
            (status, _stamp(), (result or "")[:500], command_id, device["device_id"]),
        )
        return cur.rowcount == 1
    finally:
        conn.close()
