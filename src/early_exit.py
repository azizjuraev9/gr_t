import pandas as pd
import logging
from typing import Optional
from src.data_feed import DataFeed
from src.order_manager import OrderManager

class EarlyExit:
    def __init__(self, config: dict, data_feed: DataFeed, order_manager: OrderManager):
        self.config = config
        self.data_feed = data_feed
        self.order_manager = order_manager
        self.logger = logging.getLogger(__name__)

    async def check_positions(self, symbol: str, timeframe: str) -> None:
        """Проверка позиций на риск смены тренда."""
        try:
            positions = await self.order_manager.get_open_positions(symbol)
            if not positions:
                return

            data = await self.data_feed.get_data(symbol, timeframe)
            if data.empty:
                self.logger.warning("No data for early exit check")
                return

            for position in positions:
                position_id = position["position"]["dealId"]
                direction = position["position"]["direction"]

                entry_price = position["position"]["level"]
                last_close = data["close"].iloc[-1]

                min_profit_percent = self.config.get("min_profit_percent", 0.1)

                # Рассчитываем текущую "бумажную" прибыль в процентах
                if direction == "BUY":
                    unrealized_profit = (last_close - entry_price) / entry_price * 100
                else:
                    unrealized_profit = (entry_price - last_close) / entry_price * 100

                # Если позиция ещё ни разу не достигла минимального профита — не проверяем EarlyExit
                if unrealized_profit < min_profit_percent:
                    self.logger.debug(f"Skipping early exit for {position_id}: unrealized profit {unrealized_profit:.2f}% < threshold {min_profit_percent}%")
                    continue

                # Проверка сигналов смены тренда
                if self._should_exit(data, direction):
                    await self.order_manager.close_position(position_id)
                    self.logger.info(f"Closed position {position_id} due to trend change risk")

        except Exception as e:
            self.logger.error(f"Error checking positions for early exit: {e}")

    def _should_exit(self, data: pd.DataFrame, direction: str) -> bool:
        """Проверка условий для досрочного закрытия."""
        # Пробой структуры (BOS)
        bos = self._detect_break_of_structure(data)
        if bos and ((direction == "BUY" and bos["type"] == "bearish") or
                    (direction == "SELL" and bos["type"] == "bullish")):
            return True

        # Смена характера (CHOCH)
        choch = self._detect_change_of_character(data)
        if choch and ((direction == "BUY" and choch["type"] == "bearish") or
                      (direction == "SELL" and choch["type"] == "bullish")):
            return True

        # RSI для перекупленности/перепроданности
        rsi = self._calculate_rsi(data)
        if rsi is not None:
            if direction == "BUY" and rsi > self.config["rsi_overbought"]:
                return True
            if direction == "SELL" and rsi < self.config["rsi_oversold"]:
                return True

        return False

    def _detect_break_of_structure(self, data: pd.DataFrame) -> Optional[dict]:
        data["higher_high"] = data["high"] > data["high"].shift(1)
        data["lower_low"] = data["low"] < data["low"].shift(1)
        last_candle = data.iloc[-1]
        if last_candle["higher_high"] and data["close"].iloc[-1] > data["high"].iloc[-2]:
            return {"price": last_candle["close"], "type": "bullish"}
        elif last_candle["lower_low"] and data["close"].iloc[-1] < data["low"].iloc[-2]:
            return {"price": last_candle["close"], "type": "bearish"}
        return None

    def _detect_change_of_character(self, data: pd.DataFrame) -> Optional[dict]:
        data["trend"] = data["close"].rolling(20).mean()
        last_candle = data.iloc[-1]
        if last_candle["close"] > data["trend"].iloc[-1] and data["close"].iloc[-2] < data["trend"].iloc[-2]:
            return {"price": last_candle["close"], "type": "bullish"}
        elif last_candle["close"] < data["trend"].iloc[-1] and data["close"].iloc[-2] > data["trend"].iloc[-2]:
            return {"price": last_candle["close"], "type": "bearish"}
        return None

    def _calculate_rsi(self, data: pd.DataFrame) -> Optional[float]:
        """Рассчёт RSI."""
        try:
            delta = data["close"].diff()
            gain = delta.where(delta > 0, 0).rolling(self.config["rsi_period"]).mean()
            loss = -delta.where(delta < 0, 0).rolling(self.config["rsi_period"]).mean()
            loss = loss.replace(0, 1e-10)  # избегаем деления на 0

            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.iloc[-1]
        except Exception as e:
            self.logger.error(f"Error calculating RSI: {e}")
            return None