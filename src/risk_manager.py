import logging

class RiskManager:
    def __init__(self, max_risk_per_trade: float, account_balance: float):
        self.max_risk_per_trade = max_risk_per_trade  # % риска на сделку
        self.account_balance = account_balance
        self.logger = logging.getLogger(__name__)

    def calculate_position_size(self, entry_price: float, stop_loss: float) -> float:
        """Расчёт размера позиции на основе риска."""
        try:
            risk_amount = self.account_balance * self.max_risk_per_trade
            risk_per_unit = abs(entry_price - stop_loss)
            if risk_per_unit == 0:
                self.logger.warning("Invalid stop loss, setting size to 0")
                return 0.0
            size = risk_amount / risk_per_unit
            self.logger.info(f"Calculated position size: {size} for risk {risk_amount}")
            return round(size, 2)
        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return 0.0

    def update_balance(self, new_balance: float) -> None:
        """Обновление баланса."""
        self.account_balance = new_balance
        self.logger.info(f"Account balance updated to {new_balance}")