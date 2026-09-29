import logging

logging.basicConfig(level=logging.INFO)

class Kim:
    def __init__(self):
        self.role = "Day-to-Day Trading & Account Manager"
        self.broker_name = "Vault Markets"
        self.account_id = "VM-Live"
        self.balance = 0.00
        self.floating_pl = 0.00
        self.trades_won = 0
        self.trades_lost = 0

    def get_success_rate(self):
        total = self.trades_won + self.trades_lost
        if total == 0: return 0.0
        return round((self.trades_won / total) * 100, 1)

    def update_telemetry(self, broker, acc_id, balance, pl, won, lost):
        self.broker_name = broker
        self.account_id = acc_id
        self.balance = float(balance)
        self.floating_pl = float(pl)
        self.trades_won = int(won)
        self.trades_lost = int(lost)
        return "Kim: Telemetry updated successfully."
