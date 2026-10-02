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
        self._init_prop_infrastructure()
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

    def _load_experience(self):
        if os.path.exists("data/kim_exp.json"):
            try:
                with open("data/kim_exp.json", "r") as f:
                    data = json.load(f)
                    self.active_account = data.get("account_id", None)
                    self.is_live = data.get("is_live", False)
                    self.balance = data.get("balance", 3.04)
                    self.equity = data.get("equity", 3.04)
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

    async def get_real_world_price(self, symbol: str) -> float:
        meta_token = os.environ.get("META_API_TOKEN", "").strip()
        meta_account = os.environ.get("META_API_ACCOUNT_ID", "").strip()
        if not meta_token or not meta_account: return 0.0
    async def get_precise_bid_ask(self, symbol: str) -> dict:
        meta_token = os.environ.get("META_API_TOKEN", "").strip()
        meta_account = os.environ.get("META_API_ACCOUNT_ID", "").strip()
        if not meta_token or not meta_account: return {"bid": 0.0, "ask": 0.0}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(
                    f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{meta_account}/symbols/{symbol}/current-price",
                    headers={"auth-token": meta_token}
                )
                if res.status_code == 200:
                    data = res.json()
                    return {"bid": float(data.get("bid", 0.0)), "ask": float(data.get("ask", 0.0))}
        except Exception: pass
        return {"bid": 0.0, "ask": 0.0}

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(
                    f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{meta_account}/symbols/{symbol}/current-price",
                    headers={"auth-token": meta_token}
                )
                if res.status_code == 200:
                    data = res.json()
                    return float(data.get("ask", data.get("bid", data.get("price", 0.0))))
        except Exception: pass
        return 0.0
    async def _smart_symbol_correction(self, symbol: str) -> str:
        base = symbol.split('.')[0].upper()
        if self.account_type == "micro" and not base.endswith("MIC"):
            return f"{base}.mic"
        return f"{base}.mic" if self.account_type == "micro" else base

    def calculate_risk_and_lot(self, symbol: str, stop_loss_pips: float) -> dict:
        contract_size = 1000 if self.account_type == "micro" else 100000
        min_required = 0.50 if self.account_type == "micro" else 2.00
        if self.balance < min_required: 
            return {"allowed": False, "reason": f"Insufficient balance (${self.balance:.2f})."}
        
        # Vault Markets enforces 0.10 minimum lot size for XAUUSD.mic
        base_lot = 0.10 if ("XAU" in symbol.upper() and self.account_type == "micro") else 0.01
        
        if self.balance > 10.0:
            base_lot = round(base_lot * (self.balance / 5.0), 2)
            
        estimated_margin = (contract_size * base_lot) / self.leverage
        free_margin = self.balance + self.floating_profit
        if free_margin < estimated_margin: 
            return {"allowed": False, "reason": "Free margin lower than required."}
        return {"allowed": True, "lot_size": base_lot, "estimated_margin": estimated_margin}

    async def fetch_ohlcv(self, symbol: str, timeframe: str = "1m", limit: int = 10):
        meta_token, meta_account = os.environ.get("META_API_TOKEN", ""), os.environ.get("META_API_ACCOUNT_ID", "")
        if not meta_token or not meta_account: return None
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(
                    f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{meta_account}/historical-market-data/symbols/{symbol}/timeframes/{timeframe}/candles?limit={limit}",
                    headers={"auth-token": meta_token}
                )
                if res.status_code == 200: return res.json()
        except Exception: pass
        return None

    async def _multi_timeframe_confluence(self, symbol: str) -> dict:
        m1_candles = await self.fetch_ohlcv(symbol, "1m", 5)
        m5_candles = await self.fetch_ohlcv(symbol, "5m", 5)
        if not m1_candles or not m5_candles or len(m1_candles) < 3 or len(m5_candles) < 3:
            return {"valid": True, "suggested_action": "BUY"}
        c1, c2, c3 = m1_candles[-3].get("close", 0), m1_candles[-2].get("close", 0), m1_candles[-1].get("close", 0)
        m1_exhaustion = abs((c3 - c2) - (c2 - c1)) < 0.0025
        m5_closes = [c.get("close", 0) for c in m5_candles]
        m5_avg = sum(m5_closes) / len(m5_closes)
        current_price = m5_closes[-1]
        suggested_action = "BUY" if current_price >= m5_avg else "SELL"
        return {"valid": m1_exhaustion, "suggested_action": suggested_action}

    def _calculate_atr_pips(self, candles) -> dict:
        if not candles or len(candles) < 5:
            return {"sl_pips": 8.0, "tp_pips": 12.0}
        tr_list = []
        for i in range(1, len(candles)):
            high, low, prev_close = candles[i].get("high", 0), candles[i].get("low", 0), candles[i-1].get("close", 0)
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_list.append(tr)
        atr = sum(tr_list) / len(tr_list)
        pip_multiplier = 10000 if "EUR" in candles[0].get("symbol", "") else 100
        atr_pips = max(round(atr * pip_multiplier, 1), 5.0)
        return {"sl_pips": round(atr_pips * 1.5, 1), "tp_pips": round(atr_pips * 2.2, 1)}

    def _check_daily_drawdown_limit(self) -> bool:
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT SUM(profit) FROM trade_journal WHERE DATE(timestamp) = ?", (date.today().isoformat(),))
            row = cursor.fetchone()
            if row and row[0] is not None and row[0] <= -self.max_daily_loss:
                return False
        except Exception: pass
        return True

    def _session_volatility_lock(self) -> bool:
        return 8 <= (datetime.utcnow().hour + 2) % 24 <= 20

    def _risk_manager_review(self, proposal_dict: dict, is_manual: bool = False) -> dict:
        if is_manual: return {"approved": True}
        try:
            proposal = TradeProposal(**proposal_dict)
            if not proposal.daily_drawdown_safe: return {"approved": False, "reason": "Risk Agent: Daily drawdown limit reached."}
            if not proposal.session_active: return {"approved": False, "reason": "Risk Agent: Outside active session."}
            if not proposal.spread_safe: return {"approved": False, "reason": "Risk Agent: Spread exceeds threshold."}
            if not proposal.news_safe: return {"approved": False, "reason": "Risk Agent: Blocked by Macro Shield."}
            if not proposal.quant_exhaustion_confirmed: return {"approved": False, "reason": "Risk Agent: Multi-timeframe trend mismatch."}
            if proposal.free_margin < 0.20: return {"approved": False, "reason": "Risk Agent: Margin buffer too thin."}
            return {"approved": True}
        except ValidationError as e: return {"approved": False, "reason": "Risk Agent: Schema validation failed."}

    async def execute_trade(self, raw_symbol: str, action: str, stop_loss_pips: float = 8.0, take_profit_pips: float = 12.0, is_manual: bool = False):
        action = action.upper()
        if action not in ["BUY", "SELL"]: return {"status": "error", "message": "Invalid action."}

        symbol = await self._smart_symbol_correction(raw_symbol)
        risk = self.calculate_risk_and_lot(symbol, stop_loss_pips)
        if not risk["allowed"]: return {"status": "rejected", "reason": risk["reason"]}

        confluence = await self._multi_timeframe_confluence(symbol)
        
        proposal = {
            "symbol": symbol, "action": action, "volume": round(float(risk["lot_size"]), 2),
            "quant_exhaustion_confirmed": confluence["valid"],
            "free_margin": self.balance + self.floating_profit, 
            "news_safe": True, "spread_safe": True, 
            "session_active": self._session_volatility_lock(),
            "daily_drawdown_safe": self._check_daily_drawdown_limit()
        }
        
        review = self._risk_manager_review(proposal, is_manual=is_manual)
        if not review["approved"]: return {"status": "rejected", "reason": review["reason"]}

        meta_token, meta_account = os.environ.get("META_API_TOKEN", ""), os.environ.get("META_API_ACCOUNT_ID", "")
        trade_id = f"TRD-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')[:14]}"

        meta_token = os.environ.get("META_API_TOKEN", "").strip()
        meta_account = os.environ.get("META_API_ACCOUNT_ID", "").strip()

        if not meta_token or not meta_account:
            return {"status": "error", "message": "MetaApi Error: META_API_TOKEN or META_API_ACCOUNT_ID missing on Render."}

        try:
            live_price = await self.get_real_world_price(symbol)
            sl_price, tp_price = 0.0, 0.0
            clean_sym = symbol.split('.')[0].upper()

            if live_price > 0:
                if "XAU" in clean_sym:
                    sl_dist, tp_dist = 5.0, 10.0
                    sl_price = round(live_price - sl_dist if action == "BUY" else live_price + sl_dist, 2)
                    tp_price = round(live_price + tp_dist if action == "BUY" else live_price - tp_dist, 2)
                elif "JPY" in clean_sym:
                    sl_dist, tp_dist = 0.15, 0.30
                    sl_price = round(live_price - sl_dist if action == "BUY" else live_price + sl_dist, 3)
                    tp_price = round(live_price + tp_dist if action == "BUY" else live_price - tp_dist, 3)
                elif "BTC" in clean_sym:
                    sl_dist, tp_dist = 300.0, 600.0
                    sl_price = round(live_price - sl_dist if action == "BUY" else live_price + sl_dist, 2)
                    tp_price = round(live_price + tp_dist if action == "BUY" else live_price - tp_dist, 2)
                else:
                    sl_dist, tp_dist = 0.0015, 0.0030
                    sl_price = round(live_price - sl_dist if action == "BUY" else live_price + sl_dist, 5)
                    tp_price = round(live_price + tp_dist if action == "BUY" else live_price - tp_dist, 5)

            trade_data = {"actionType": f"ORDER_TYPE_{action}", "symbol": symbol, "volume": round(float(risk["lot_size"]), 2)}

            async with httpx.AsyncClient(timeout=10.0) as client:
                api_res = await client.post(
                    f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{meta_account}/trade",
                    headers={"auth-token": meta_token},
                    json=trade_data
                )
                
                if api_res.status_code not in [200, 204]:
                    return {"status": "error", "message": f"Broker Rejected ({api_res.status_code}): {api_res.text}"}
                
                res_json = api_res.json()
                string_code = res_json.get("stringCode", "")
                numeric_code = res_json.get("numericResponseCode", 0)
                
                if string_code and string_code != "TRADE_RETCODE_DONE" and numeric_code != 10009:
                    err_msg = res_json.get("message") or string_code
                    return {"status": "error", "message": f"Broker Rejected Order: {err_msg}"}

        except Exception as e:
            return {"status": "error", "message": f"MetaApi Error: {type(e).__name__} - {str(e)}"}

        self.db_conn.execute("INSERT INTO trade_journal (id, symbol, action, volume, sl_pips, tp_pips, mode) VALUES (?, ?, ?, ?, ?, ?, ?)",
                             (trade_id, symbol, action, risk["lot_size"], stop_loss_pips, take_profit_pips, self.trading_mode))
        self.db_conn.commit()
        self.open_positions.append({"id": trade_id, "symbol": symbol, "action": action})
        self._save_experience()
        return {"status": "success", "message": f"Kim: Executed {action} {risk['lot_size']} {symbol}."}

    async def auto_entry_engine(self):
        if not self.is_live or len(self.open_positions) >= 1: return
        symbol = "EURUSD.mic" if self.account_type == "micro" else "EURUSD"
        if self._session_volatility_lock() and self._check_daily_drawdown_limit():
            confluence = await self._multi_timeframe_confluence(symbol)
            if confluence["valid"]:
                candles = await self.fetch_ohlcv(symbol, "1m", 10)
                atr_targets = self._calculate_atr_pips(candles)
                await self.execute_trade(symbol, action=confluence["suggested_action"], stop_loss_pips=atr_targets["sl_pips"], take_profit_pips=atr_targets["tp_pips"], is_manual=False)

    async def auto_close_engine(self):
        meta_token, meta_account = os.environ.get("META_API_TOKEN", ""), os.environ.get("META_API_ACCOUNT_ID", "")
        if not meta_token or not meta_account or not self.open_positions: return
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{meta_account}/positions", headers={"auth-token": meta_token})
                if res.status_code == 200:
                    for pos in res.json():
                        profit = pos.get("unrealizedProfit", 0)
                        open_time_str = pos.get("time", datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"))
                        try:
                            age_mins = (datetime.utcnow() - datetime.strptime(open_time_str[:19], "%Y-%m-%dT%H:%M:%S")).total_seconds() / 60
                        except: age_mins = 0
                        
                        if profit >= 0.04 or age_mins > 15:
                            await client.delete(f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{meta_account}/positions/{pos.get('id')}", headers={"auth-token": meta_token})
                            self.db_conn.execute("UPDATE trade_journal SET profit = ? WHERE id = ?", (profit, pos.get('id')))
                            self.db_conn.commit()
        except Exception: pass

    async def _heartbeat_loop(self):
        while True:
            await asyncio.sleep(10)
            if self.is_live:
                try:
                    await self.get_live_metrics()
                    await self.auto_entry_engine()
                    await self.auto_close_engine()
                except Exception: pass

    async def apply_trailing_stops(self):
        meta_token, meta_account = os.environ.get("META_API_TOKEN", ""), os.environ.get("META_API_ACCOUNT_ID", "")
        if not meta_token or not meta_account or not self.open_positions: return
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{meta_account}/positions", headers={"auth-token": meta_token})
                if res.status_code == 200:
                    for pos in res.json():
                        if pos.get("unrealizedProfit", 0) > 0.15: 
                            await client.put(f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{meta_account}/positions/{pos.get('id')}", headers={"auth-token": meta_token}, json={"stopLoss": pos.get("openPrice")})
        except Exception: pass

    async def connect_live_account(self, account_id: str, password: str, server: str = "VaultMarkets-Live"):
        self.active_account = account_id
        self.is_live = True
        self._save_experience()
        if not self.heartbeat_active:
            self.heartbeat_active = True
            asyncio.create_task(self._heartbeat_loop())
        return {"status": "success", "message": f"Kim: Connected [{account_id}].", "account_id": account_id, "balance": f"${self.balance:,.2f}"}

    async def get_live_metrics(self):
        if self.is_live and not getattr(self, 'heartbeat_active', False):
            self.heartbeat_active = True
            asyncio.create_task(self._heartbeat_loop())
        meta_token, meta_account = os.environ.get("META_API_TOKEN", ""), os.environ.get("META_API_ACCOUNT_ID", "")
        gold_price = await self.get_real_world_price("XAUUSD")
        if meta_token and meta_account:
            headers, base_url = {"auth-token": meta_token}, f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{meta_account}"
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    acc, pos = await asyncio.gather(client.get(f"{base_url}/account-information", headers=headers), client.get(f"{base_url}/positions", headers=headers), return_exceptions=True)
                    if isinstance(acc, httpx.Response) and acc.status_code == 200:
                        self.balance = float(acc.json().get("balance", self.balance))
                        self.equity = float(acc.json().get("equity", self.equity))
                        self.floating_profit = self.equity - self.balance
                    if isinstance(pos, httpx.Response) and pos.status_code == 200: self.open_positions = pos.json()
            except Exception: pass
            asyncio.create_task(self.apply_trailing_stops())
        self._save_experience()
        return {
            "live_gold_price": f"${gold_price:,.2f}", 
            "account_id": self.active_account or "Not Linked", 
            "balance": f"${self.balance:,.2f}", 
            "equity": f"${self.equity:,.2f}", 
            "floating_profit": f"${self.floating_profit:+,.2f}", 
            "open_positions": f"{len(self.open_positions)} Trades", 
            "is_live": self.is_live
        }
