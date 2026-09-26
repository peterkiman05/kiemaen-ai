#!/usr/bin/env python3
import os, sys, httpx

BASE_URL = os.environ.get("AUTO_EVOLVE_URL", "http://localhost:8081")
TOKEN = os.environ.get("AUTO_EVOLVE_TOKEN")

def _headers():
    if not TOKEN:
        print("ERROR: AUTO_EVOLVE_TOKEN not set."); sys.exit(1)
    return {"x-admin-token": TOKEN}

def list_suggestions():
    r = httpx.get(f"{BASE_URL}/admin/list", headers=_headers()); r.raise_for_status()
    data = r.json().get("suggestions", [])
    if not data: print("No suggestions in queue."); return
    for s in data:
        print(f"[{s['id']}] ({s['status']}) {s['description']} -> {s['action']}")

def approve(sid): print(httpx.post(f"{BASE_URL}/admin/approve/{sid}", headers=_headers()).json())
def rollback(sid): print(httpx.post(f"{BASE_URL}/admin/rollback/{sid}", headers=_headers()).json())
def health(): print(httpx.get(f"{BASE_URL}/admin/health", headers=_headers()).json())

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: admin_cli.py [list|approve <id>|rollback <id>|health]"); sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "list": list_suggestions()
    elif cmd == "approve" and len(sys.argv) == 3: approve(sys.argv[2])
    elif cmd == "rollback" and len(sys.argv) == 3: rollback(sys.argv[2])
    elif cmd == "health": health()
    else: print("Usage: admin_cli.py [list|approve <id>|rollback <id>|health]")
