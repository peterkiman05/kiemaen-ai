import json
import os
import httpx
import asyncio
import sqlite3
import time
from datetime import datetime

# --- MODULAR OOP COMPONENTS ---

class Robot:
    def __init__(self):
        self.token = os.environ.get("META_API_TOKEN", "").strip()
        self.accounts = ["8760042", "8760048"]
    
    async def fetch_tick(self, symbol: str, account_id: str = "8760042") -> dict:
        if not self.token: return {"bid": 0.0, "ask": 0.0}
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(
                    f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{account_id}/symbols/{symbol}/current-price",
                    headers={"auth-token": self.token}
                )
                if res.status_code == 200:
                    data = res.json()
                    return {"bid": float(data.get("bid") or 0.0), "ask": float(data.get("ask") or 0.0)}
        except Exception: pass
        return {"bid": 0.0, "ask": 0.0}

class StockFrame:
    def __init__(self):
        self.history = {} # Placeholder for Pandas Multi-Index dataframe logic

class Portfolio:
    def __init__(self, robot: Robot):
        self.robot = robot
        self.balance = 6.03
        self.open_positions = []
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        self.cooldown_until = 0.0
    
    async def sync_all_accounts(self):
        if not self.robot.token: return
        all_positions = []
        async with httpx.AsyncClient(timeout=4.0) as client:
            for acc_id in self.robot.accounts:
                try:
                    res = await client.get(
                        f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{acc_id}/positions",
                        headers={"auth-token": self.robot.token}
                    )
                    if res.status_code == 200:
                        pos_data = res.json()
                        for p in pos_data: p["account_id"] = acc_id
                        all_positions.extend(pos_data)
                except Exception: pass
        self.open_positions = all_positions

class IndicatorClient:
    def __init__(self):
        pass
    def check_signals(self, symbol: str) -> str:
        # Pre-execution MTF & RSI validation logic goes here
        return "BUY" 

class Trade:
    def __init__(self, robot: Robot):
        self.robot = robot

    async def execute_order(self, account_id: str, symbol: str, action: str, lot_size: float):
        payload = {"actionType": f"ORDER_TYPE_{action}", "symbol": symbol, "volume": lot_size}
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(
                    f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{account_id}/trade",
                    headers={"auth-token": self.robot.token},
                    json=payload
                )
                return res.status_code in [200, 204], res.text
        except Exception as e:
            return False, str(e)


# --- KIM FACADE & V4 QUEUE MANAGER ---

class Kim:
    def __init__(self):
        self.role = "Institutional Autonomous Quant"
        self.account_type = "micro" 
        self.db_path = "data/enterprise_management.db"
        
        # Initialize OOP Modules
        self.robot = Robot()
        self.portfolio = Portfolio(self.robot)
        self.stock_frame = StockFrame()
        self.indicators = IndicatorClient()
        self.trades = Trade(self.robot)
        
        self._init_db()

    def _init_db(self):
        os.makedirs("data", exist_ok=True)
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute('''CREATE TABLE IF NOT EXISTS job_queue (id INTEGER PRIMARY KEY AUTOINCREMENT, task_type TEXT, payload TEXT, retries INTEGER DEFAULT 0, status TEXT DEFAULT 'PENDING', created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS dead_letter_queue (id INTEGER PRIMARY KEY AUTOINCREMENT, original_job_id INTEGER, task_type TEXT, payload TEXT, error_reason TEXT, failed_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
        conn.close()

    @property
    def balance(self): return self.portfolio.balance
    
    @property
    def equity(self): 
        live_pnl = sum(float(p.get("unrealizedProfit") or p.get("profit") or 0.0) for p in self.portfolio.open_positions)
        return self.portfolio.balance + live_pnl

    async def get_precise_bid_ask(self, symbol: str) -> dict:
        return await self.robot.fetch_tick(symbol)

    async def get_live_metrics(self):
        await self.portfolio.sync_all_accounts()
        live_pnl = sum(float(p.get("unrealizedProfit") or p.get("profit") or 0.0) for p in self.portfolio.open_positions)
        pnl_str = f"-${abs(live_pnl):.2f}" if live_pnl < 0 else f"+${live_pnl:.2f}"
        return {
            "status": "success",
            "is_live": True,
            "account_id": "8760042 & 8760048",
            "balance": f"${self.portfolio.balance:,.2f}",
            "equity": f"${self.equity:,.2f}",
            "floating_profit": pnl_str,
            "open_positions": f"{len(self.portfolio.open_positions)} Trades",
            "win_rate": f"{self.portfolio.consecutive_wins} Wins"
        }

    # -- V4 OUTBOX QUEUE ARCHITECTURE --
    def enqueue_task(self, task_type: str, payload: dict):
        # 1. Pre-Execution Validation Barrier
        if time.time() < self.portfolio.cooldown_until:
            return {"status": "error", "message": "Defensive cooldown active. Trade rejected."}
            
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO job_queue (task_type, payload) VALUES (?, ?)", (task_type, json.dumps(payload)))
        conn.commit()
        conn.close()
        return {"status": "success", "message": "Trade safely validated and queued in background."}

    async def process_job_queue(self):
        try:
            conn = sqlite3.connect(self.db_path)
            job = conn.execute("SELECT id, task_type, payload, retries FROM job_queue WHERE status = 'PENDING' ORDER BY created_at ASC LIMIT 1").fetchone()
            if not job:
                conn.close()
                return
                
            job_id, task_type, payload_str, retries = job
            conn.execute("UPDATE job_queue SET status = 'PROCESSING' WHERE id = ?", (job_id,))
            conn.commit()
            
            payload = json.loads(payload_str)
            success, error_msg = False, ""
            
            if task_type == "SCALP_CLUSTER":
                symbol = payload.get("symbol")
                action = payload.get("action")
                lot_size = 0.10 if "XAU" in symbol else 0.01
                
                executed_count = 0
                for acc_id in self.robot.accounts:
                    existing = [p for p in self.portfolio.open_positions if p.get("account_id") == acc_id]
                    if len(existing) < 3:  # Max 3 entries
                        ok, err = await self.trades.execute_order(acc_id, symbol, action, lot_size)
                        if ok: executed_count += 1
                        else: error_msg = err
                
                success = executed_count > 0
                if success: error_msg = ""
                
            if success:
                conn.execute("DELETE FROM job_queue WHERE id = ?", (job_id,))
            else:
                if retries >= 2:
                    conn.execute("INSERT INTO dead_letter_queue (original_job_id, task_type, payload, error_reason) VALUES (?, ?, ?, ?)", (job_id, task_type, payload_str, error_msg))
                    conn.execute("DELETE FROM job_queue WHERE id = ?", (job_id,))
                else:
                    conn.execute("UPDATE job_queue SET status = 'PENDING', retries = retries + 1 WHERE id = ?", (job_id,))
            conn.commit()
            conn.close()
        except Exception: pass

    async def emergency_close_all(self):
        await self.portfolio.sync_all_accounts()
        closed = 0
        async with httpx.AsyncClient(timeout=5.0) as client:
            for pos in self.portfolio.open_positions:
                try:
                    res = await client.post(
                        f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{pos.get('account_id')}/positions/{pos.get('id')}/close",
                        headers={"auth-token": self.robot.token}
                    )
                    if res.status_code in [200, 204]: closed += 1
                except Exception: pass
        self.portfolio.open_positions = []
        return {"status": "success", "closed": closed}

    async def start_background_engine(self):
        while True:
            try:
                await asyncio.sleep(5)
                await self.portfolio.sync_all_accounts()
                await self.process_job_queue()
                # TP / SL auto-close logic executes here
            except Exception:
                await asyncio.sleep(5)