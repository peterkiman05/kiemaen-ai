import json
import os
import httpx
import asyncio
import sqlite3
from datetime import datetime, date
from pydantic import BaseModel, ValidationError

class TradeProposal(BaseModel):
    symbol: str
    action: str
    volume: float
    quant_exhaustion_confirmed: bool
    free_margin: float
    news_safe: bool
    spread_safe: bool
    session_active: bool
    daily_drawdown_safe: bool

class Kim:
    def __init__(self):
        self.role = "Institutional Autonomous Quant"
        self.broker_name = "Vault Markets"
        self.evolution_level = 5
        self.is_live = False
        self.active_account = None
        self.balance = 3.04
        self.equity = 3.04
        self.leverage = 500
        self.open_positions = []
        self.floating_profit = 0.0
        self.trading_mode = "scalper" 
        self.account_type = "micro" 
        self.analysis_speed_ms = 200
        self.heartbeat_active = False
        self.news_block_active = False
        self.max_daily_loss = 0.45
        self.db_path = "data/enterprise_management.db"
        self._init_prop_infrastructure()
        self._init_enterprise_management_db()
        self._load_experience()

    def _init_prop_infrastructure(self):
        os.makedirs("data", exist_ok=True)
        self.db_conn = sqlite3.connect("data/kim_performance.db", check_same_thread=False)
        self.db_conn.execute('''
            CREATE TABLE IF NOT EXISTS trade_journal (
                id TEXT PRIMARY KEY, symbol TEXT, action TEXT, 
                volume REAL, sl_pips REAL, tp_pips REAL, 
                mode TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                profit REAL DEFAULT 0.0
            )
        ''')
        self.db_conn.commit()

    def _init_enterprise_management_db(self):
        os.makedirs("data", exist_ok=True)
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS active_trades (
                ticket_id TEXT PRIMARY KEY,
                symbol TEXT,
                action TEXT,
                volume REAL,
                status TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS corporate_tasks (
                task_id TEXT PRIMARY KEY,
                assigned_agent TEXT,
                directive TEXT,
                status TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def _load_experience(self):
        if os.path.exists("data/kim_exp.json"):
            try:
                with open("data/kim_exp.json", "r") as f:
                    data = json.load(f)
                    self.active_account = data.get("account_id", None)
                    self.is_live = data.get("is_live", False)
                    self.balance = float(data.get("balance") or 3.04)
                    self.equity = float(data.get("equity") or 3.04)
                    self.trading_mode = data.get("trading_mode", "scalper")
                    self.account_type = data.get("account_type", "micro")
            except Exception: pass

    def _save_experience(self):
        os.makedirs("data", exist_ok=True)
        with open("data/kim_exp.json", "w") as f:
            json.dump({
                "account_id": self.active_account, "is_live": self.is_live, 
                "balance": self.balance, "equity": self.equity, 
                "trading_mode": self.trading_mode, "account_type": self.account_type
            }, f)

    async def get_precise_bid_ask(self, symbol: str) -> dict:
        token = os.environ.get("META_API_TOKEN", "").strip()
        account_id = os.environ.get("META_API_ACCOUNT_ID", "").strip()
        if not token or not account_id: return {"bid": 0.0, "ask": 0.0}
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(
                    f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{account_id}/symbols/{symbol}/current-price",
                    headers={"auth-token": token}
                )
                if res.status_code == 200:
                    data = res.json()
                    return {"bid": float(data.get("bid") or 0.0), "ask": float(data.get("ask") or 0.0)}
        except Exception: pass
        return {"bid": 0.0, "ask": 0.0}

    async def get_real_world_price(self, symbol: str) -> float:
        tick = await self.get_precise_bid_ask(symbol)
        return tick.get("ask") or tick.get("bid") or 0.0

    async def _smart_symbol_correction(self, symbol: str) -> str:
        base = symbol.split('.')[0].upper()
        return f"{base}.mic" if self.account_type == "micro" else base

    def calculate_risk_and_lot(self, symbol: str, stop_loss_pips: float) -> dict:
        contract_size = 1000 if self.account_type == "micro" else 100000
        min_required = 0.50 if self.account_type == "micro" else 2.00
        if self.balance < min_required: 
            return {"allowed": False, "reason": f"Insufficient balance (${self.balance:.2f})."}
        
        base_lot = 0.10 if ("XAU" in symbol.upper() and self.account_type == "micro") else 0.01
        if self.balance > 10.0:
            base_lot = round(base_lot * (self.balance / 5.0), 2)
            
        estimated_margin = (contract_size * base_lot) / self.leverage
        free_margin = self.balance + self.floating_profit
        if free_margin < estimated_margin: 
            return {"allowed": False, "reason": "Free margin lower than required."}
        return {"allowed": True, "lot_size": base_lot, "estimated_margin": estimated_margin}

    async def reconcile_positions(self):
        token = os.environ.get("META_API_TOKEN", "").strip()
        account_id = os.environ.get("META_API_ACCOUNT_ID", "").strip()
        if not token or not account_id: return

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(
                    f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{account_id}/positions",
                    headers={"auth-token": token}
                )
                if res.status_code == 200:
                    live_positions = res.json()
                    self.open_positions = live_positions
                    live_ids = {str(p.get("id")) for p in live_positions if p.get("id")}

                    conn = sqlite3.connect(self.db_path, check_same_thread=False)
                    cursor = conn.cursor()
                    cursor.execute("SELECT ticket_id FROM active_trades WHERE status = 'OPEN'")
                    db_tickets = [row[0] for row in cursor.fetchall()]

                    for ticket in db_tickets:
                        if ticket not in live_ids:
                            cursor.execute("UPDATE active_trades SET status = 'CLOSED' WHERE ticket_id = ?", (ticket,))
                    conn.commit()
                    conn.close()
        except Exception: pass

    async def execute_trade(self, raw_symbol: str, action: str, stop_loss_pips: float = 8.0, take_profit_pips: float = 12.0, is_manual: bool = False):
        action = action.upper()
        if action not in ["BUY", "SELL"]: return {"status": "error", "message": "Invalid action."}

        symbol = await self._smart_symbol_correction(raw_symbol)
        risk = self.calculate_risk_and_lot(symbol, stop_loss_pips)
        if not risk["allowed"]: return {"status": "rejected", "reason": risk["reason"]}

        token = os.environ.get("META_API_TOKEN", "").strip()
        account_id = os.environ.get("META_API_ACCOUNT_ID", "").strip()
        if not token or not account_id:
            return {"status": "error", "message": "MetaApi credentials missing on Render."}

        clean_volume = round(float(risk["lot_size"]), 2)
        payload = {
            "actionType": f"ORDER_TYPE_{action}",
            "symbol": symbol,
            "volume": clean_volume
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{account_id}/trade",
                    headers={"auth-token": token},
                    json=payload
                )
                res_data = res.json() if res.status_code in [200, 204] else {}
                string_code = res_data.get("stringCode", "")
                numeric_code = res_data.get("numericResponseCode", 0)

                if string_code == "TRADE_RETCODE_DONE" or numeric_code == 10009:
                    ticket_id = str(res_data.get("orderId") or res_data.get("numericResponseCode") or "EXEC")
                    conn = sqlite3.connect(self.db_path, check_same_thread=False)
                    conn.execute(
                        "INSERT OR REPLACE INTO active_trades (ticket_id, symbol, action, volume, status) VALUES (?, ?, ?, ?, 'OPEN')",
                        (ticket_id, symbol, action, clean_volume)
                    )
                    conn.commit()
                    conn.close()
                    self._save_experience()
                    return {"status": "success", "message": f"Kim: Executed {action} {clean_volume} {symbol} [Ticket #{ticket_id}]."}
                else:
                    reason = res_data.get("message") or string_code or f"HTTP {res.status_code}"
                    return {"status": "error", "message": f"Broker Rejected Order: {reason}"}
        except Exception as e:
            return {"status": "error", "message": f"MetaApi Error: {type(e).__name__} - {str(e)}"}

    async def get_live_metrics(self):
        token = os.environ.get("META_API_TOKEN", "").strip()
        account_id = os.environ.get("META_API_ACCOUNT_ID", "").strip()
        if token and account_id:
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    acc = await client.get(
                        f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{account_id}/account-information",
                        headers={"auth-token": token}
                    )
                    if acc.status_code == 200:
                        data = acc.json()
                        self.balance = float(data.get("balance") or self.balance)
                        self.equity = float(data.get("equity") or self.equity)
                        self.floating_profit = self.equity - self.balance
            except Exception: pass
        
        await self.reconcile_positions()
        self._save_experience()
        return {
            "account_id": self.active_account or "Linked",
            "balance": f"${self.balance:,.2f}",
            "equity": f"${self.equity:,.2f}",
            "floating_profit": f"${self.floating_profit:+,.2f}",
            "open_positions": f"{len(self.open_positions)} Trades",
            "is_live": True
        }

    async def start_background_engine(self):
        while True:
            try:
                await asyncio.sleep(5)
                await self.reconcile_positions()
                await self.get_live_metrics()
            except Exception:
                await asyncio.sleep(5)
