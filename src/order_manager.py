import logging
from typing import Optional, List
from src.client import CapitalClient
from src.config import load_config

class OrderManager:
    def __init__(self, client: CapitalClient):
        self.client = client
        self.config = load_config("config.yaml")
        self.logger = logging.getLogger(__name__)

    async def place_order(self, symbol: str, direction: str, size: float, price: Optional[float] = None,
                          stop_loss: Optional[float] = None, take_profit: Optional[float] = None) -> None:
        try:
            if self.config["mode"] == "backtest":
                self.logger.info(f"Simulated order: {symbol}, {direction}, size={size}, price={price}, SL={stop_loss}, TP={take_profit}")
                return
            result = self.client.place_order(symbol, direction, size, price, stop_loss, take_profit)
            if result:
                self.logger.info(f"Order placed successfully: {result}")
            else:
                self.logger.warning("Order placement failed")
        except Exception as e:
            self.logger.error(f"Error placing order: {e}")

    async def close_position(self, position_id: str) -> None:
        """Закрытие позиции по ID."""
        try:
            if self.config["mode"] == "backtest":
                self.logger.info(f"Simulated position close: {position_id}")
                return
            response = self.client.session.delete(
                f"{self.client.base_url}/positions/{position_id}"
            )
            response.raise_for_status()
            self.logger.info(f"Position {position_id} closed successfully")
        except Exception as e:
            self.logger.error(f"Error closing position {position_id}: {e}")

    async def get_open_positions(self, symbol: str) -> List:
        """Получение списка открытых позиций."""
        try:
            if self.config["mode"] == "backtest":
                return []  # В бэктесте позиции обрабатываются Backtester
            response = self.client.session.get(f"{self.client.base_url}/positions")
            response.raise_for_status()
            positions = response.json().get("positions", [])
            filtered_positions = [p for p in positions if p["market"]["epic"] == symbol]
            self.logger.debug(f"Fetched positions: {filtered_positions}")
            return filtered_positions
        except Exception as e:
            self.logger.error(f"Error fetching positions: {str(e)}")
            return []