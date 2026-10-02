import json
import os
import httpx
import asyncio
import sqlite3
from datetime import datetime
from pydantic import BaseModel

class Kim:
    def __init__(self):
        self.role = "Institutional Autonomous Quant"
        self.broker_name = "Vault Markets"
        self.evolution_level = 5
        self.is_live = False
        self.active_account = None
        self.balance = 6.03
        self.equity = 6.03
        self.leverage = 500
        self.open_positions = []
        self.floating_profit = 0.0
        self.trading_mode = "scalper" 
        self.account_type = "micro" 
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
                ticket_id TEXT PRIMARY KEY, symbol TEXT, action TEXT, volume REAL, status TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS executive_metrics (
                metric_key TEXT PRIMARY KEY, metric_value TEXT, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
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
                    self.balance = float(data.get("balance") or 6.03)
                    self.equity = float(data.get("equity") or 6.03)
            except Exception: pass

    def _save_experience(self):
        os.makedirs("data", exist_ok=True)
        with open("data/kim_exp.json", "w") as f:
            json.dump({"account_id": self.active_account, "balance": self.balance, "equity": self.equity}, f)

    def _is_trading_paused(self) -> bool:
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("SELECT metric_value FROM executive_metrics WHERE metric_key = 'TRADING_PAUSED'")
            row = cursor.fetchone()
            conn.close()
            return row[0].upper() == "TRUE" if row else False
        except Exception:
            return False

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

    def calculate_risk_and_lot(self, symbol: str, stop_loss_pips: float = 8.0) -> dict:
        base_lot = 0.10 if ("XAU" in symbol.upper() and self.account_type == "micro") else 0.01
        return {"allowed": True, "lot_size": base_lot}

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
                    self.open_positions = res.json()
        except Exception: pass

    async def auto_manage_and_close_profits(self):
        token = os.environ.get("META_API_TOKEN", "").strip()
        account_id = os.environ.get("META_API_ACCOUNT_ID", "").strip()
        if not token or not account_id or not self.open_positions: return

        for pos in self.open_positions:
            pos_id = pos.get("id")
            unrealized = float(pos.get("unrealizedProfit") or pos.get("profit") or 0.0)
            if unrealized >= 0.15 and pos_id:
                try:
                    async with httpx.AsyncClient(timeout=4.0) as client:
                        await client.post(
                            f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{account_id}/positions/{pos_id}/close",
                            headers={"auth-token": token}
                        )
                except Exception: pass

    async def execute_trade(self, raw_symbol: str, action: str, stop_loss_pips: float = 8.0, is_manual: bool = False):
        action = action.upper()
        symbol = f"{raw_symbol.split('.')[0].upper()}.mic" if self.account_type == "micro" else raw_symbol.upper()
        risk = self.calculate_risk_and_lot(symbol)
        
        token = os.environ.get("META_API_TOKEN", "").strip()
        account_id = os.environ.get("META_API_ACCOUNT_ID", "").strip()
        if not token or not account_id:
            return {"status": "error", "message": "MetaApi credentials missing on Render."}

        clean_volume = round(float(risk["lot_size"]), 2)
        payload = {"actionType": f"ORDER_TYPE_{action}", "symbol": symbol, "volume": clean_volume}

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
                    ticket_id = str(res_data.get("orderId") or "EXEC")
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
                if not self._is_trading_paused():
                    await self.reconcile_positions()
                    await self.get_live_metrics()
                    await self.auto_manage_and_close_profits()
            except Exception:
                await asyncio.sleep(5)
