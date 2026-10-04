import json
import os
import httpx
import asyncio
import sqlite3
import time
from datetime import datetime
import pandas as pd

class Robot:
    def __init__(self):
        self.token = os.environ.get("META_API_TOKEN", "").strip()
        self.accounts = []
    
    async def fetch_tick(self, symbol: str, account_id: str = "8760042") -> dict:
        if not self.token:
            raise Exception("META_API_TOKEN is not configured.")
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(
                "https://mt-client-api-v1.new-york.agiliumtrade.ai/users/current/accounts/" + account_id + "/symbols/" + symbol + "/current-price",
                headers={"auth-token": self.token}
            )
            if res.status_code == 200:
                data = res.json()
                return {"bid": float(data.get("bid") or 0.0), "ask": float(data.get("ask") or 0.0)}
            else:
                raise Exception("Failed to fetch tick: " + res.text)

class StockFrame:
    def __init__(self):
        index = pd.MultiIndex.from_tuples([], names=["symbol", "timestamp"])
        self.history = pd.DataFrame(columns=["open", "high", "low", "close", "volume"], index=index)

    def append_tick(self, symbol: str, price: float):
        now = pd.Timestamp.utcnow()
        self.history.loc[(symbol, now), :] = [price, price, price, price, 0]
        self.history = self.history.sort_index()
        if len(self.history) > 5000:
            self.history = self.history.iloc[-5000:]

class IndicatorClient:
    def __init__(self, stock_frame: StockFrame):
        self.stock_frame = stock_frame

    def check_signals(self, symbol: str) -> str:
        try:
            if symbol not in self.stock_frame.history.index.get_level_values("symbol"):
                return "HOLD"
            
            df = self.stock_frame.history.xs(symbol, level="symbol")
            if len(df) < 14:
                return "HOLD"
            
            close_prices = pd.to_numeric(df["close"])
            ema_20 = close_prices.ewm(span=20, adjust=False).mean().iloc[-1]
            ema_50 = close_prices.ewm(span=50, adjust=False).mean().iloc[-1]
            current_price = close_prices.iloc[-1]

            if ema_20 > ema_50 and current_price > ema_20:
                return "BUY"
            elif ema_20 < ema_50 and current_price < ema_20:
                return "SELL"
            return "HOLD"
        except Exception as e:
            print("Indicator calculation error: " + str(e))
            return "HOLD"

class Portfolio:
    def __init__(self, robot: Robot):
        self.robot = robot
        self.balance = 0.0
        self.open_positions = []
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        self.cooldown_until = 0.0
    
    async def sync_all_accounts(self):
        if not self.robot.token:
            raise Exception("META_API_TOKEN is missing. Portfolio cannot sync.")
        
        all_positions = []
        total_balance = 0.0
        
        async with httpx.AsyncClient(timeout=8.0) as client:
            for acc_id in self.robot.accounts:
                res_pos = await client.get(
                    "https://mt-client-api-v1.new-york.agiliumtrade.ai/users/current/accounts/" + acc_id + "/positions",
                    headers={"auth-token": self.robot.token}
                )
                if res_pos.status_code == 200:
                    pos_data = res_pos.json()
                    for p in pos_data: 
                        p["account_id"] = acc_id
                    all_positions.extend(pos_data)
                else:
                    raise Exception("Failed to sync positions for account " + acc_id + ". " + res_pos.text)
                
                res_acc = await client.get(
                    "https://mt-client-api-v1.new-york.agiliumtrade.ai/users/current/accounts/" + acc_id + "/account-information",
                    headers={"auth-token": self.robot.token}
                )
                if res_acc.status_code == 200:
                    acc_info = res_acc.json()
                    total_balance += float(acc_info.get("balance", 0.0))
                else:
                    raise Exception("Failed to sync balance for account " + acc_id + ". " + res_acc.text)

        self.open_positions = all_positions
        if total_balance > 0:
            self.balance = total_balance

class Trade:
    def __init__(self, robot: Robot):
        self.robot = robot

    async def execute_order(self, account_id: str, symbol: str, action: str, lot_size: float):
        tsl_dist = 1.5 if "XAU" in symbol else 0.0015
        payload = {
            "actionType": "ORDER_TYPE_" + action, 
            "symbol": symbol, 
            "volume": lot_size,
            "trailingStopLoss": {
                "distance": {
                    "distance": tsl_dist,
                    "units": "RELATIVE_PRICE"
                }
            }
        }
        async with httpx.AsyncClient(timeout=8.0) as client:
            res = await client.post(
                "https://mt-client-api-v1.new-york.agiliumtrade.ai/users/current/accounts/" + account_id + "/trade",
                headers={"auth-token": self.robot.token},
                json=payload
            )
            if res.status_code in [200, 204]:
                return True, res.text
            else:
                return False, "Broker Error: " + res.text

class Kim:
    def __init__(self):
        self.role = "Institutional Autonomous Quant"
        self.account_type = "micro" 
        self.db_path = "data/enterprise_management.db"
        
        self.robot = Robot()
        self.portfolio = Portfolio(self.robot)
        self.stock_frame = StockFrame()
        self.indicators = IndicatorClient(self.stock_frame)
        self.trades = Trade(self.robot)
        
        self._init_db()

    
    def update_credentials(self, token: str, accounts: list):
        self.robot.token = token.strip()
        self.robot.accounts = [a.strip() for a in accounts if a.strip()]
        self.portfolio.open_positions = []
        self.portfolio.balance = 0.0

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
        try:
            tick = await self.robot.fetch_tick(symbol)
            if tick.get("bid", 0.0) > 0:
                self.stock_frame.append_tick(symbol, tick["bid"])
            return tick
        except Exception:
            return {"bid": 0.0, "ask": 0.0}

    async def get_live_metrics(self):
        try:
            await self.portfolio.sync_all_accounts()
            live_pnl = sum(float(p.get("unrealizedProfit") or p.get("profit") or 0.0) for p in self.portfolio.open_positions)
            pnl_str = "-$" + "{:.2f}".format(abs(live_pnl)) if live_pnl < 0 else "+$" + "{:.2f}".format(live_pnl)
            return {
                "status": "success",
                "is_live": True,
                "account_id": "8760042 & 8760048",
                "balance": "$" + "{:,.2f}".format(self.portfolio.balance),
                "equity": "$" + "{:,.2f}".format(self.equity),
                "floating_profit": pnl_str,
                "open_positions": str(len(self.portfolio.open_positions)) + " Trades",
                "win_rate": str(self.portfolio.consecutive_wins) + " Wins"
            }
        except Exception as e:
            return {"status": "error", "message": "Metrics unavailable: " + str(e)}

    def enqueue_task(self, task_type: str, payload: dict):
        if time.time() < self.portfolio.cooldown_until:
            return {"status": "error", "message": "Defensive cooldown active. Trade rejected."}
            
        utc_hour = datetime.utcnow().hour
        if 22 <= utc_hour or utc_hour < 1:
            return {"status": "error", "message": "Market in highly illiquid rollover period (22:00-01:00 UTC). Execution guarded."}
        
        symbol = payload.get("symbol", "")
        signal = self.indicators.check_signals(symbol)
        if signal == "HOLD":
            return {"status": "error", "message": "Trade rejected. Indicator confluence suggests HOLD."}
            
        payload["action"] = signal
            
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO job_queue (task_type, payload) VALUES (?, ?)", (task_type, json.dumps(payload)))
        conn.commit()
        conn.close()
        return {"status": "success", "message": "Trade securely validated and queued in background."}

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
                
                eq = self.equity
                base_lot = 0.01
                if eq > 20.0: 
                    base_lot = round(eq / 2000, 2)
                if base_lot < 0.01: 
                    base_lot = 0.01
                
                lot_size = round(base_lot * 2, 2) if "XAU" in symbol else base_lot
                
                executed_count = 0
                for acc_id in self.robot.accounts:
                    existing = [p for p in self.portfolio.open_positions if p.get("account_id") == acc_id]
                    if len(existing) < 3: 
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
        try:
            await self.portfolio.sync_all_accounts()
        except Exception:
            pass
        closed = 0
        async with httpx.AsyncClient(timeout=8.0) as client:
            for pos in self.portfolio.open_positions:
                try:
                    res = await client.post(
                        "https://mt-client-api-v1.new-york.agiliumtrade.ai/users/current/accounts/" + pos.get("account_id") + "/positions/" + pos.get("id") + "/close",
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
            except Exception as e:
                print("Engine Exception: " + str(e))
                await asyncio.sleep(5)