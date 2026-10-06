
import os
import json
import glob
import sqlite3
import hashlib
import datetime
import jwt
import httpx
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Kiemaen AI & Kim Quant Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MASTER_TOKEN = "eyJhbGciOiJSUzUxMiIsInR5cCI6IkpXVCJ9.eyJfaWQiOiJjYThlYjJmZWQwN2Y3NTY4ZjM1NDdhMTA3N2Y2MDA4MCIsImFjY2Vzc1J1bGVzIjpbeyJpZCI6InRyYWRpbmctYWNjb3VudC1tYW5hZ2VtZW50LWFwaSIsIm1ldGhvZHMiOlsidHJhZGluZy1hY2NvdW50LW1hbmFnZW1lbnQtYXBpOnJlc3Q6cHVibGljOio6KiJdLCJyb2xlcyI6WyJyZWFkZXIiLCJ3cml0ZXIiXSwicmVzb3VyY2VzIjpbIio6JFVTRVJfSUQkOioiXX0seyJpZCI6Im1ldGFhcGktcmVzdC1hcGkiLCJtZXRob2RzIjpbIm1ldGFhcGktYXBpOnJlc3Q6cHVibGljOio6KiJdLCJyb2xlcyI6WyJyZWFkZXIiLCJ3cml0ZXIiXSwicmVzb3VyY2VzIjpbIio6JFVTRVJfSUQkOioiXX0seyJpZCI6Im1ldGFhcGktcnBjLWFwaSIsIm1ldGhvZHMiOlsibWV0YWFwaS1hcGk6d3M6cHVibGljOio6KiJdLCJyb2xlcyI6WyJyZWFkZXIiLCJ3cml0ZXIiXSwicmVzb3VyY2VzIjpbIio6JFVTRVJfSUQkOioiXX0seyJpZCI6Im1ldGFhcGktcmVhbC10aW1lLXN0cmVhbWluZy1hcGkiLCJtZXRob2RzIjpbIm1ldGFhcGktYXBpOndzOnB1YmxpYzoqOioiXSwicm9sZXMiOlsicmVhZGVyIiwid3JpdGVyIl0sInJlc291cmNlcyI6WyIqOiRVU0VSX0lEJDoqIl19LHsiaWQiOiJtZXRhc3RhdHMtYXBpIiwibWV0aGhvZHMiOlsibWV0YXN0YXRzLWFwaTpyZXN0OnB1YmxpYzoqOioiXSwicm9sZXMiOlsicmVhZGVyIiwid3JpdGVyIl0sInJlc291cmNlcyI6WyIqOiRVU0VSX0lEJDoqIl19LHsiaWQiOiJyaXNrLW1hbmFnZW1lbnQtYXBpIiwibWV0aGhvZHMiOlsicmlzay1tYW5hZ2VtZW50LWFwaTpyZXN0OnB1YmxpYzoqOioiXSwicm9sZXMiOlsicmVhZGVyIiwid3JpdGVyIl0sInJlc291cmNlcyI6WyIqOiRVU0VSX0lEJDoqIl19LHsiaWQiOiJjb3B5ZmFjdG9yeS1hcGkiLCJtZXRob2RzIjpbIm1ldGFwaS1hcGk6cmVzdDpwdWJsaWM6KjoqIl0sInJvbGVzIjpbInJlYWRlciIsIndyaXRlciJdLCJyZXNvdXJjZXMiOlsiKjokVVNFUl9JRCQ6KiJdfV0sImlnbm9yZVJhdGVMaW1pdHMiOmZhbHNlLCJ0b2tlbklkIjoiMjAyMTAyMTMiLCJpbXBlcnNvbmF0ZWQiOmZhbHNlLCJyZWFsVXNlcklkIjoiY2E4ZWIyZmVkMDdmNzU2OGYzNTQ3YTEwNzdmNjAwODAiLCJpYXQiOjE3OTExNzcyNzZ9.KsjqvmeRobyGViT4zS5k5iVJbxui5CoOZBD0Ru6Q1pyEUsjPgQkCCcKJ-dxYGzMNl9Rta-FdUEWVzhKEoiYEkPSMsGHBrOC5WYSYkr-iUO1WbXO9_x1C-hYr-56QJJKPcm8CwrPXdf_1Mikxn_r3756YreV1q1mgNP2Rr9FhvaMZ2PuU1VHuNZts6yJVXYCotpvFbkWl2Ad0mik0DQaMTUCJf46O_3xbCeSAlUw-drSQTfPI0xPeW0SP7jAZMkuBjpImT93aK6YMhCieO4Y1ywh6e0oQLd2kvyP-MQKbBFnmeYZKI98wSWljWgFBV_HxN2XRRIDHNaRAZP9phzdY_dApmqWpzhI7wBVfRBx683mF_NXXr6wIK60p7_6XL0hd5NzGOYdEcZYocJKCbAZrETknOFInhV11PJ1Varjw8kYunX10mxyPVGV1d-u_pLxHUCfcrvaIuDYPe-gYKv5MjPgaq8oA63Vkoj39iaIEZeeunRnk-0zlkq59VktyUbtJMDG8AsI1FfnHXPwvfOpYoV8zQ5dX3ns3Fi4az4FIGiu2czBb8BbLbMaadUgDc531yjsoQIuu5cyenG32riAyCh4lRJdsG3B0KEIXDCjACgZhvcYZnNRXBWfqO6andWw13P1fkpMJiErmD90pE9iXBy-McGONC7VwReGyynkhDus"
BROKER_SERVER = "VaultMarkets-Live"

# HARDCODED PASSWORDS FOR AUTO-PROVISIONING
ACCOUNT_PASSWORDS = {
    "8760042": "MaXI-c8Q",
    "8760048": "TQ-9CcIb"
}

# --- AUTO-PROVISIONING HELPER ---
async def get_or_provision_account(client, login: str):
    headers = {"auth-token": MASTER_TOKEN, "Content-Type": "application/json"}
    prov_url = "https://mt-provisioning-api-v1.new-york.agiliumtrade.ai/users/current/accounts"
    
    # 1. Check if the account already exists on MetaAPI
    res = await client.get(prov_url, headers=headers)
    if res.status_code == 200:
        for acc in res.json():
            if str(acc.get("login")) == str(login):
                target_id = acc.get("_id")
                # Ensure it is actively deployed
                if acc.get("state") != "DEPLOYED":
                    await client.post(f"{prov_url}/{target_id}/deploy", headers=headers)
                    import asyncio
                    await asyncio.sleep(2)
                return target_id, "Existing account active."
                
    # 2. Provision if not found
    pwd = ACCOUNT_PASSWORDS.get(str(login))
    if not pwd: 
        return None, f"No password stored for {login}"
        
    payload = {
        "name": f"Kim-{login}",
        "login": str(login),
        "password": pwd,
        "server": BROKER_SERVER,
        "platform": "mt5",
        "magic": 100000
    }
    
    create_res = await client.post(prov_url, json=payload, headers=headers)
    if create_res.status_code in [200, 201]:
        target_id = create_res.json().get("id")
        await client.post(f"{prov_url}/{target_id}/deploy", headers=headers)
        import asyncio
        await asyncio.sleep(3) 
        return target_id, "Account deployed."
        
    # FORCE METAPI TO REVEAL THE EXACT ERROR
    return None, f"MetaAPI Rejected: [{create_res.status_code}] {create_res.text}"

# --- AUTO-PROVISIONING SYNC & EXECUTION ROUTES ---
@app.get("/api/kim/sync/{login}")
async def sync_account(login: str):
    try:
        headers = {"auth-token": MASTER_TOKEN, "Content-Type": "application/json"}
        async with httpx.AsyncClient(verify=False, timeout=20.0) as client:
            target_id, msg = await get_or_provision_account(client, login)
            if not target_id:
                return {"status": "error", "message": f"Sync Error: {msg}"}
                
            info_url = f"https://mt-client-api-v1.new-york.agiliumtrade.ai/users/current/accounts/{target_id}/account-information"
            info_res = await client.get(info_url, headers=headers)
            if info_res.status_code == 200:
                data = info_res.json()
                return {
                    "status": "success",
                    "balance": data.get("balance", 0.0),
                    "floating": data.get("profit", 0.0)
                }
            return {"status": "error", "message": f"Info Fetch Failed: {info_res.status_code}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/kim/execute_trade")
async def execute_live_trade(request: Request):
    try:
        data = await request.json()
        symbol = data.get("symbol", "XAUUSD")
        account_login = data.get("login", "8760042")
        action = data.get("action", "ORDER_TYPE_BUY")
        volume = float(data.get("volume", 0.01))
        
        headers = {"auth-token": MASTER_TOKEN, "Content-Type": "application/json"}
        
        async with httpx.AsyncClient(verify=False, timeout=25.0) as client:
            target_id, msg = await get_or_provision_account(client, account_login)
            if not target_id:
                return {"status": "error", "message": f"Setup Failed: {msg}"}
                
            trade_url = f"https://mt-client-api-v1.new-york.agiliumtrade.ai/users/current/accounts/{target_id}/trade"
            trade_payload = {"actionType": action, "symbol": symbol, "volume": volume}
            
            trade_res = await client.post(trade_url, json=trade_payload, headers=headers)
            if trade_res.status_code in [200, 201, 204]:
                return {"status": "success", "message": f"LIVE ORDER FILLED: {volume} {action} {symbol} on #{account_login}"}
            else:
                return {"status": "error", "message": f"Broker Rejected: {trade_res.text}"}
    except Exception as e:
        return {"status": "error", "message": f"Execution fault: {str(e)}"}
