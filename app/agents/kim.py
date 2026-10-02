import json
import os
import httpx
import asyncio
import sqlite3
import time
from datetime import datetime

class Kim:
    def __init__(self):
        self.role = "Institutional Autonomous Quant"
        self.broker_name = "Vault Markets"
        self.account_type = "micro" 
        self.balance = 6.03
        self.equity = 6.03
        self.open_positions = []
        self.floating_profit = 0.0
        
        # Evolution State Memory
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        self.cooldown_until = 0.0
        
        self.db_path = "data/enterprise_management.db"
        self._init_enterprise_management_db()
        self._load_experience()

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
                    self.balance = float(data.get("balance") or self.balance)
                    self.consecutive_wins = int(data.get("wins") or 0)
                    self.consecutive_losses = int(data.get("losses") or 0)
                    self.cooldown_until = float(data.get("cooldown") or 0.0)
            except Exception: pass

    def _save_experience(self):
        os.makedirs("data", exist_ok=True)
        with open("data/kim_exp.json", "w") as f:
            json.dump({
                "balance": self.balance,
                "wins": self.consecutive_wins,
                "losses": self.consecutive_losses,
                "cooldown": self.cooldown_until
            }, f)

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

    async def _fetch_tf(self, client, ticker, interval):
        try:
            res = await client.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval={interval}&range=5d", headers={"User-Agent": "Mozilla/5.0"})
            if res.status_code == 200:
                closes = [c for c in res.json()["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c is not None]
                if len(closes) >= 2: return "BUY" if closes[-1] > closes[-2] else "SELL"
        except Exception: pass
        return None

    async def analyze_multi_timeframe(self, symbol: str, strictness: str = "normal") -> str:
        clean_sym = symbol.split('.')[0].upper()
        ticker = "GC=F" if "XAU" in clean_sym else f"{clean_sym}=X"
        intervals = ["1m", "5m", "15m", "60m", "1d"]
        scores = {"BUY": 0, "SELL": 0}

        async with httpx.AsyncClient(timeout=5.0) as client:
            tasks = [self._fetch_tf(client, ticker, iv) for iv in intervals]
            results = await asyncio.gather(*tasks)

        for r in results:
            if r: scores[r] += 1

        # Evolutionary Logic Gate
        if strictness == "defensive":
            # Requires absolute macro-micro confluence
            if scores["BUY"] >= 4: return "BUY"
            if scores["SELL"] >= 4: return "SELL"
            return "HOLD"
        else:
            # Standard aggressive entry
            return "BUY" if scores["BUY"] > scores["SELL"] else "SELL"

    async def reconcile_positions(self):
        token = os.environ.get("META_API_TOKEN", "").strip()
        account_id = os.environ.get("META_API_ACCOUNT_ID", "").strip()
        if not token: return
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

        # Evolution State Targets
        target_tp = 0.15
        if self.consecutive_wins >= 2: target_tp = 0.25
        if self.consecutive_losses >= 1: target_tp = 0.08
        
        max_loss_allowed = -(self.balance * 0.30)

        for pos in self.open_positions:
            pos_id = pos.get("id")
            unrealized = float(pos.get("unrealizedProfit") or pos.get("profit") or 0.0)
            
            is_win = unrealized >= target_tp
            is_loss = unrealized <= max_loss_allowed

            if (is_win or is_loss) and pos_id:
                try:
                    async with httpx.AsyncClient(timeout=4.0) as client:
                        res = await client.post(
                            f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{account_id}/positions/{pos_id}/close",
                            headers={"auth-token": token}
                        )
                        if res.status_code in [200, 204]:
                            if is_win:
                                self.consecutive_wins += 1
                                self.consecutive_losses = 0
                            elif is_loss:
                                self.consecutive_losses += 1
                                self.consecutive_wins = 0
                                self.cooldown_until = time.time() + 600  # 10 min penalty box
                            self._save_experience()
                except Exception: pass

    async def execute_trade(self, raw_symbol: str, action: str, is_manual: bool = False):
        if time.time() < self.cooldown_until:
            wait_mins = int((self.cooldown_until - time.time()) / 60)
            return {"status": "error", "message": f"Defensive Cooldown Active: {wait_mins} mins remaining after previous loss."}

        action = action.upper()
        symbol = f"{raw_symbol.split('.')[0].upper()}.mic"
        lot_size = 0.10 if "XAU" in symbol else 0.01
        
        token = os.environ.get("META_API_TOKEN", "").strip()
        account_id = os.environ.get("META_API_ACCOUNT_ID", "").strip()
        if not token: return {"status": "error", "message": "API config missing."}

        payload = {"actionType": f"ORDER_TYPE_{action}", "symbol": symbol, "volume": lot_size}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{account_id}/trade",
                    headers={"auth-token": token},
                    json=payload
                )
                res_data = res.json() if res.status_code in [200, 204] else {}
                if res_data.get("stringCode") == "TRADE_RETCODE_DONE" or res_data.get("numericResponseCode") == 10009:
                    return {"status": "success", "message": f"Kim Executed {action} {lot_size} {symbol}"}
                else:
                    return {"status": "error", "message": f"Broker Rejected: {res_data.get('message')}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def get_live_metrics(self):
        token = os.environ.get("META_API_TOKEN", "").strip()
        account_id = os.environ.get("META_API_ACCOUNT_ID", "").strip()
        
        # 1. Pull active open positions directly from broker
        live_pnl = 0.0
        open_count = 0
        
        if token and account_id:
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    # Sync Account Info
                    acc_res = await client.get(
                        f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{account_id}/account-information",
                        headers={"auth-token": token}
                    )
                    if acc_res.status_code == 200:
                        acc_data = acc_res.json()
                        self.balance = float(acc_data.get("balance") or self.balance)
                        self.equity = float(acc_data.get("equity") or self.equity)

                    # Sync Live Positions & Sum Exact Real-Time Floating PnL
                    pos_res = await client.get(
                        f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{account_id}/positions",
                        headers={"auth-token": token}
                    )
                    if pos_res.status_code == 200:
                        self.open_positions = pos_res.json()
                        open_count = len(self.open_positions)
                        
                        # Sum exact ticket PnL (Negative if in loss, Positive if in profit)
                        live_pnl = sum(
                            float(p.get("unrealizedProfit") or p.get("profit") or 0.0) 
                            for p in self.open_positions
                        )
            except Exception: pass

        # Format floating profit cleanly (e.g. -$0.42 or +$0.15)
        pnl_str = f"-${abs(live_pnl):.2f}" if live_pnl < 0 else f"+${live_pnl:.2f}"

        return {
            "status": "success",
            "is_live": True,
            "account_id": getattr(self, "active_account", "8760042") or "8760042",
            "balance": f"${self.balance:,.2f}",
            "equity": f"${(self.balance + live_pnl):,.2f}",
            "floating_profit": pnl_str,
            "open_positions": f"{open_count} Trades",
            "win_rate": f"{getattr(self, 'consecutive_wins', 0)} Wins"
        }",
            "equity": f"${self.equity:,.2f}",
            "floating_profit": f"${floating:+,.2f}",
            "open_positions": f"{len(getattr(self, 'open_positions', []))} Trades",
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
