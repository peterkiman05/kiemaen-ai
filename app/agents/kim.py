import json
import os
import httpx
import asyncio
import sqlite3
import time

class Kim:
    def __init__(self):
        self.role = "Institutional Autonomous Quant"
        self.broker_name = "Vault Markets"
        self.account_type = "micro" 
        self.balance = 6.03
        self.equity = 6.03
        self.open_positions = []
        
        # Multi-Account Registry
        self.accounts = ["8760042", "8760048"]
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        self.cooldown_until = 0.0
        
        self.db_path = "data/enterprise_management.db"
        self._init_db()

    def _init_db(self):
        os.makedirs("data", exist_ok=True)
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS active_trades (
                ticket_id TEXT PRIMARY KEY, account_id TEXT, symbol TEXT, action TEXT, volume REAL, status TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    async def get_precise_bid_ask(self, symbol: str) -> dict:
        token = os.environ.get("META_API_TOKEN", "").strip()
        account_id = os.environ.get("META_API_ACCOUNT_ID", "8760042").strip()
        if not token or not account_id: return {"bid": 0.0, "ask": 0.0}
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(
                    f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{account_id}/symbols/{symbol}/current-price",
                    headers={"auth-token": token}
                )
                if res.status_code == 200:
                    data = res.json()
                    return {"bid": float(data.get("bid") or 0.0), "ask": float(data.get("ask") or 0.0)}
        except Exception: pass
        return {"bid": 0.0, "ask": 0.0}

    async def reconcile_positions(self):
        token = os.environ.get("META_API_TOKEN", "").strip()
        if not token: return
        all_positions = []
        
        async with httpx.AsyncClient(timeout=4.0) as client:
            for acc_id in self.accounts:
                try:
                    res = await client.get(
                        f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{acc_id}/positions",
                        headers={"auth-token": token}
                    )
                    if res.status_code == 200:
                        positions = res.json()
                        for p in positions:
                            p["account_id"] = acc_id
                        all_positions.extend(positions)
                except Exception: pass
        self.open_positions = all_positions

    async def auto_manage_and_close_profits(self):
        token = os.environ.get("META_API_TOKEN", "").strip()
        if not token or not self.open_positions: return

        target_tp = 0.15
        if self.consecutive_wins >= 2: target_tp = 0.25
        if self.consecutive_losses >= 1: target_tp = 0.08
        
        max_loss_allowed = -(self.balance * 0.30)

        async with httpx.AsyncClient(timeout=4.0) as client:
            for pos in self.open_positions:
                pos_id = pos.get("id")
                acc_id = pos.get("account_id", "8760042")
                unrealized = float(pos.get("unrealizedProfit") or pos.get("profit") or 0.0)
                
                is_win = unrealized >= target_tp
                is_loss = unrealized <= max_loss_allowed

                if (is_win or is_loss) and pos_id:
                    try:
                        await client.post(
                            f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{acc_id}/positions/{pos_id}/close",
                            headers={"auth-token": token}
                        )
                        if is_win:
                            self.consecutive_wins += 1
                            self.consecutive_losses = 0
                        elif is_loss:
                            self.consecutive_losses += 1
                            self.consecutive_wins = 0
                            self.cooldown_until = time.time() + 300
                    except Exception: pass

    async def execute_scalp_cluster(self, raw_symbol: str, action: str, max_entries: int = 3):
        if time.time() < self.cooldown_until:
            return {"status": "error", "message": "Defensive Cooldown Active after previous loss."}

        token = os.environ.get("META_API_TOKEN", "").strip()
        if not token: return {"status": "error", "message": "MetaApi Token missing."}

        action = action.upper()
        symbol = f"{raw_symbol.split('.')[0].upper()}.mic"
        lot_size = 0.10 if "XAU" in symbol else 0.01

        executed_count = 0
        async with httpx.AsyncClient(timeout=8.0) as client:
            for acc_id in self.accounts:
                # Check current open count for account
                existing = [p for p in self.open_positions if p.get("account_id") == acc_id]
                slots_available = max(0, max_entries - len(existing))
                
                for _ in range(slots_available):
                    payload = {"actionType": f"ORDER_TYPE_{action}", "symbol": symbol, "volume": lot_size}
                    try:
                        res = await client.post(
                            f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{acc_id}/trade",
                            headers={"auth-token": token},
                            json=payload
                        )
                        if res.status_code in [200, 204]:
                            executed_count += 1
                    except Exception: pass

        return {"status": "success", "message": f"Fired {executed_count} scalp entries across linked accounts."}

    async def emergency_close_all(self):
        token = os.environ.get("META_API_TOKEN", "").strip()
        if not token or not self.open_positions:
            return {"status": "success", "closed": 0}

        closed_count = 0
        async with httpx.AsyncClient(timeout=5.0) as client:
            for pos in self.open_positions:
                pos_id = pos.get("id")
                acc_id = pos.get("account_id", "8760042")
                if pos_id:
                    try:
                        res = await client.post(
                            f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{acc_id}/positions/{pos_id}/close",
                            headers={"auth-token": token}
                        )
                        if res.status_code in [200, 204]:
                            closed_count += 1
                    except Exception: pass
        self.open_positions = []
        return {"status": "success", "closed": closed_count}

    async def get_live_metrics(self):
        token = os.environ.get("META_API_TOKEN", "").strip()
        live_pnl = 0.0
        
        if token:
            try:
                await self.reconcile_positions()
                live_pnl = sum(float(p.get("unrealizedProfit") or p.get("profit") or 0.0) for p in self.open_positions)
            except Exception: pass

        pnl_str = f"-${abs(live_pnl):.2f}" if live_pnl < 0 else f"+${live_pnl:.2f}"
        return {
            "status": "success",
            "is_live": True,
            "account_id": "8760042 & 8760048",
            "balance": f"${self.balance:,.2f}",
            "equity": f"${(self.balance + live_pnl):,.2f}",
            "floating_profit": pnl_str,
            "open_positions": f"{len(self.open_positions)} Trades",
            "win_rate": f"{self.consecutive_wins} Wins"
        }

    async def start_background_engine(self):
        while True:
            try:
                await asyncio.sleep(5)
                await self.reconcile_positions()
                await self.get_live_metrics()
                await self.auto_manage_and_close_profits()
            except Exception:
                await asyncio.sleep(5)
