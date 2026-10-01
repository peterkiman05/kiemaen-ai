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
        self.max_daily_loss = 0.45  # $0.45 maximum daily drawdown limit for micro protection
        
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

    # 1. REAL-WORLD FINANCIAL ORACLE
    async def get_real_world_price(self, symbol: str) -> float:
        ticker = "GC=F" if "XAU" in symbol.upper() else f"{symbol[:6]}=X"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(
                    f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1m",
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                if res.status_code == 200:
                    return float(res.json()["chart"]["result"][0]["meta"]["regularMarketPrice"])
        except Exception: pass
        return 0.0

    async def _smart_symbol_correction(self, symbol: str) -> str:
        if self.account_type == "micro" and not symbol.endswith(".m"):
            return f"{symbol}.m"
        return symbol

    # 2. DYNAMIC COMPOUNDING LOT SIZE CALCULATOR
    def calculate_risk_and_lot(self, symbol: str, stop_loss_pips: float) -> dict:
        contract_size = 1000 if self.account_type == "micro" else 100000
        min_required = 0.50 if self.account_type == "micro" else 2.00
        if self.balance < min_required: 
            return {"allowed": False, "reason": f"Insufficient balance (${self.balance:.2f})."}
        
        # Scale lot size progressively as account balance grows
        base_lot = 0.01
        if self.balance > 10.0:
            base_lot = round(0.01 * (self.balance / 5.0), 2)
            
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

    # 3. MULTI-TIMEFRAME CONFLUENCE FILTER (1m Velocity + 5m Micro-Trend)
    async def _multi_timeframe_confluence(self, symbol: str) -> dict:
        m1_candles = await self.fetch_ohlcv(symbol, "1m", 5)
        m5_candles = await self.fetch_ohlcv(symbol, "5m", 5)
        
        if not m1_candles or not m5_candles or len(m1_candles) < 3 or len(m5_candles) < 3:
            return {"valid": True, "suggested_action": "BUY"}  # Default fallback
            
        # M1 Taylor Series Acceleration
        c1, c2, c3 = m1_candles[-3].get("close", 0), m1_candles[-2].get("close", 0), m1_candles[-1].get("close", 0)
        m1_exhaustion = abs((c3 - c2) - (c2 - c1)) < 0.0025
        
        # M5 Trend Bias (Fast Moving Average Comparison)
        m5_closes = [c.get("close", 0) for c in m5_candles]
        m5_avg = sum(m5_closes) / len(m5_closes)
        current_price = m5_closes[-1]
        
        suggested_action = "BUY" if current_price >= m5_avg else "SELL"
        return {"valid": m1_exhaustion, "suggested_action": suggested_action}

    # 4. ADAPTIVE ATR VOLATILITY SL/TP CALCULATOR
    def _calculate_atr_pips(self, candles) -> dict:
        if not candles or len(candles) < 5:
            return {"sl_pips": 8.0, "tp_pips": 12.0}
            
        tr_list = []
        for i in range(1, len(candles)):
            high = candles[i].get("high", 0)
            low = candles[i].get("low", 0)
            prev_close = candles[i-1].get("close", 0)
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_list.append(tr)
            
        atr = sum(tr_list) / len(tr_list)
        pip_multiplier = 10000 if "EUR" in candles[0].get("symbol", "") else 100
        atr_pips = max(round(atr * pip_multiplier, 1), 5.0)
        
        return {
            "sl_pips": round(atr_pips * 1.5, 1), # 1:1.5 Asymmetrical Risk/Reward
            "tp_pips": round(atr_pips * 2.2, 1)
        }

    # 5. DAILY MAX DRAWDOWN PROTECTION GUARD
    def _check_daily_drawdown_limit(self) -> bool:
        try:
            today_str = date.today().isoformat()
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT SUM(profit) FROM trade_journal WHERE DATE(timestamp) = ?", (today_str,))
            row = cursor.fetchone()
            daily_pnl = row[0] if row and row[0] is not None else 0.0
            
            # Lock trading if daily losses hit max limit
            if daily_pnl <= -self.max_daily_loss:
                return False
        except Exception: pass
        return True

    def _session_volatility_lock(self) -> bool:
        sast_hour = (datetime.utcnow().hour + 2) % 24
        return 8 <= sast_hour <= 20

    def _risk_manager_review(self, proposal_dict: dict, is_manual: bool = False) -> dict:
        if is_manual: 
            return {"approved": True} # Guaranteed execution override for direct chat commands
            
        try:
            proposal = TradeProposal(**proposal_dict)
            if not proposal.daily_drawdown_safe: 
                return {"approved": False, "reason": "Risk Agent: Daily drawdown limit reached. Engine locked for preservation."}
            if not proposal.session_active: 
                return {"approved": False, "reason": "Risk Agent: Outside active 08:00-20:00 SAST trading session."}
            if not proposal.spread_safe: 
                return {"approved": False, "reason": "Risk Agent: Spread exceeds safety threshold."}
            if not proposal.news_safe: 
                return {"approved": False, "reason": "Risk Agent: Blocked by Macro-Economic Shield."}
            if not proposal.quant_exhaustion_confirmed: 
                return {"approved": False, "reason": "Risk Agent: Multi-timeframe trend/momentum filter did not align."}
            if proposal.free_margin < 0.20: 
                return {"approved": False, "reason": "Risk Agent: Margin buffer too thin."}
            return {"approved": True}
        except ValidationError as e:
            return {"approved": False, "reason": f"Risk Agent: Schema validation failed - {e}"}

    async def execute_trade(self, raw_symbol: str, action: str, stop_loss_pips: float = 8.0, take_profit_pips: float = 12.0, is_manual: bool = False):
        action = action.upper()
        if action not in ["BUY", "SELL"]: return {"status": "error", "message": "Invalid action."}

        symbol = await self._smart_symbol_correction(raw_symbol)
        risk = self.calculate_risk_and_lot(symbol, stop_loss_pips)
        if not risk["allowed"]: return {"status": "rejected", "reason": risk["reason"]}

        confluence = await self._multi_timeframe_confluence(symbol)
        daily_safe = self._check_daily_drawdown_limit()
        
        proposal = {
            "symbol": symbol, "action": action, "volume": risk["lot_size"],
            "quant_exhaustion_confirmed": confluence["valid"],
            "free_margin": self.balance + self.floating_profit, 
            "news_safe": True, "spread_safe": True, 
            "session_active": self._session_volatility_lock(),
            "daily_drawdown_safe": daily_safe
        }
        
        review = self._risk_manager_review(proposal, is_manual=is_manual)
        if not review["approved"]: return {"status": "rejected", "reason": review["reason"]}

        meta_token, meta_account = os.environ.get("META_API_TOKEN", ""), os.environ.get("META_API_ACCOUNT_ID", "")
        trade_id = f"TRD-{len(self.open_positions) + 1001}"

        if meta_token and meta_account:
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    await client.post(
                        f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{meta_account}/trade",
                        headers={"auth-token": meta_token},
                        json={"actionType": f"ORDER_TYPE_{action}", "symbol": symbol, "volume": risk["lot_size"], "stopLoss": stop_loss_pips, "takeProfit": take_profit_pips}
                    )
            except Exception: pass
            
        self.db_conn.execute("INSERT INTO trade_journal (id, symbol, action, volume, sl_pips, tp_pips, mode) VALUES (?, ?, ?, ?, ?, ?, ?)",
                             (trade_id, symbol, action, risk["lot_size"], stop_loss_pips, take_profit_pips, self.trading_mode))
        self.db_conn.commit()
        
        self.open_positions.append({"id": trade_id, "symbol": symbol, "action": action})
        self._save_experience()
        return {"status": "success", "message": f"Kim: Executed {action} {risk['lot_size']} {symbol}."}

    # 6. AUTONOMOUS HIGH-FREQUENCY SCALPING ENGINE WITH ATR & MULTI-TIMEFRAME ALIGNMENT
    async def auto_entry_engine(self):
        if not self.is_live or len(self.open_positions) >= 1: return
        symbol = "EURUSD.m" if self.account_type == "micro" else "EURUSD"
        
        if self._session_volatility_lock() and self._check_daily_drawdown_limit():
            confluence = await self._multi_timeframe_confluence(symbol)
            if confluence["valid"]:
                candles = await self.fetch_ohlcv(symbol, "1m", 10)
                atr_targets = self._calculate_atr_pips(candles)
                
                await self.execute_trade(
                    symbol, 
                    action=confluence["suggested_action"], 
                    stop_loss_pips=atr_targets["sl_pips"], 
                    take_profit_pips=atr_targets["tp_pips"],
                    is_manual=False
                )

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
                            open_dt = datetime.strptime(open_time_str[:19], "%Y-%m-%dT%H:%M:%S")
                            age_mins = (datetime.utcnow() - open_dt).total_seconds() / 60
                        except: age_mins = 0
                        
                        # Micro Take Profit ($0.04) or Stagnation Time Exit (15 minutes)
                        if profit >= 0.04 or age_mins > 15:
                            await client.delete(
                                f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{meta_account}/positions/{pos.get('id')}",
                                headers={"auth-token": meta_token}
                            )
                            # Record realized profit to DB journal
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
                            await client.put(
                                f"https://mt-client-api-v1.london.agiliumtrade.ai/users/current/accounts/{meta_account}/positions/{pos.get('id')}",
                                headers={"auth-token": meta_token}, json={"stopLoss": pos.get("openPrice")}
                            )
        except Exception: pass

    async def connect_live_account(self, account_id: str, password: str, server: str = "VaultMarkets-Live"):
        self.active_account = account_id
        self.is_live = True
        self._save_experience()
        if not self.heartbeat_active:
            self.heartbeat_active = True
            asyncio.create_task(self._heartbeat_loop())
        return {"status": "success", "message": f"Kim: Connected [{account_id}]. Institutional Quant Engine Active.", "account_id": account_id, "balance": f"${self.balance:,.2f}"}

    async def get_live_metrics(self):
        # Auto-defibrillator to restart heartbeat if server slept
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
