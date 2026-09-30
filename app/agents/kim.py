import json
import os
import httpx

class Kim:
    def __init__(self):
        self.role = "Day-to-Day Trading & Quantitative Manager"
        self.broker_name = "Vault Markets"
        self.is_live = False
        self.active_account = None
        self.balance = 0.0
        self.equity = 0.0
        self.open_positions = []
        self.floating_profit = 0.0
        self._load_experience()

    def _load_experience(self):
        if os.path.exists("data/kim_exp.json"):
            try:
                with open("data/kim_exp.json", "r") as f:
                    data = json.load(f)
                    self.active_account = data.get("account_id", None)
                    self.is_live = data.get("is_live", False)
                    self.balance = data.get("balance", 0.0)
                    self.equity = data.get("equity", 0.0)
                    self.floating_profit = data.get("floating_profit", 0.0)
            except Exception:
                pass

    def _save_experience(self):
        os.makedirs("data", exist_ok=True)
        with open("data/kim_exp.json", "w") as f:
            json.dump({
                "account_id": self.active_account,
                "is_live": self.is_live,
                "balance": self.balance,
                "equity": self.equity,
                "floating_profit": self.floating_profit
            }, f)

    async def get_live_metrics(self):
        """Fetches real-time metrics from the live MetaApi MT5 gateway if configured."""
        meta_token = os.environ.get("META_API_TOKEN", "")
        meta_account = os.environ.get("META_API_ACCOUNT_ID", "")

        if meta_token and meta_account:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    # Fetch live account information
                    res = await client.get(
                        f"https://mt-client-api-v1.agiliumtrade.agiliumtrade.ai/users/current/accounts/{meta_account}/account-information",
                        headers={"auth-token": meta_token}
                    )
                    if res.status_code == 200:
                        data = res.json()
                        self.balance = float(data.get("balance", self.balance))
                        self.equity = float(data.get("equity", self.balance))
                        self.floating_profit = self.equity - self.balance

                    # Fetch live open positions
                    pos_res = await client.get(
                        f"https://mt-client-api-v1.agiliumtrade.agiliumtrade.ai/users/current/accounts/{meta_account}/positions",
                        headers={"auth-token": meta_token}
                    )
                    if pos_res.status_code == 200:
                        self.open_positions = pos_res.json()
            except Exception as e:
                print(f"Kim Bridge Error: {e}")

        self._save_experience()

        return {
            "account_id": self.active_account or "Not Linked",
            "balance": f"${self.balance:,.2f}",
            "equity": f"${self.equity:,.2f}",
            "open_positions": f"{len(self.open_positions)} Active Trades",
            "floating_profit": f"${self.floating_profit:+,.2f}",
            "is_live": self.is_live and bool(meta_token)
        }

    async def update_telemetry_direct(self, balance: float, equity: float, open_trades_count: int):
        """Direct push endpoint for real-time local MT5 bridges."""
        self.balance = balance
        self.equity = equity
        self.floating_profit = equity - balance
        self.open_positions = [{} for _ in range(open_trades_count)]
        self._save_experience()
        return {"status": "updated", "balance": self.balance, "equity": self.equity}
