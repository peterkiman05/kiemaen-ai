"""Scoped Android companion enrollment and device-token helpers.

Device tokens are random, stored only as SHA-256 hashes, and limited to
identifying/heartbeating a paired companion. This module does not execute
phone commands or grant remote-control capabilities.
"""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .auth import DB_PATH

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _connect():
    conn = sqlite3.connect(str(DB_PATH), timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS device_agents (
            device_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            device_name TEXT NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            last_seen_at TEXT,
            revoked_at TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_device_agents_user ON device_agents(user_id)")
    return conn

def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def pair_device(user_id: int, device_name: str) -> dict:
    name = " ".join((device_name or "").strip().split())[:80] or "Android device"
    device_id = str(uuid.uuid4())
    token = secrets.token_urlsafe(48)
    conn = _connect()
    try:
        conn.execute(
            """INSERT INTO device_agents
               (device_id,user_id,device_name,token_hash,created_at)
               VALUES (?,?,?,?,?)""",
            (device_id, user_id, name, _token_hash(token), _now()),
        )
        conn.commit()
        return {"device_id": device_id, "device_name": name, "device_token": token}
    finally:
        conn.close()

def list_devices(user_id: int) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT device_id,device_name,created_at,last_seen_at,revoked_at
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
            """UPDATE device_agents SET revoked_at=?
               WHERE device_id=? AND user_id=? AND revoked_at IS NULL""",
            (_now(), device_id, user_id),
        )
        conn.commit()
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
        conn.execute(
            "UPDATE device_agents SET last_seen_at=? WHERE device_id=?",
            (_now(), row["device_id"]),
        )
        conn.commit()
        return dict(row)
    finally:
        conn.close()
