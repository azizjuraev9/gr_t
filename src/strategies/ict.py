import pandas as pd
import logging
from typing import Optional, Dict
from src.data_feed import DataFeed
from src.order_manager import OrderManager
from src.risk_manager import RiskManager
from src.stop_loss_take_profit import StopLossTakeProfit
from src.early_exit import EarlyExit
from src.config import load_config
from datetime import datetime, time
import asyncio

class ICTStrategy:
    def __init__(self, symbol: str, timeframe: str, data_feed: DataFeed, order_manager: OrderManager,
                 risk_manager: RiskManager, sl_tp_calculator: StopLossTakeProfit, early_exit: EarlyExit,
                 config: Dict):
        self.symbol = symbol
        self.timeframe = timeframe
        self.data_feed = data_feed
        self.order_manager = order_manager
        self.risk_manager = risk_manager
        self.sl_tp_calculator = sl_tp_calculator
        self.early_exit = early_exit
        self.config = config
        self.global_config = load_config("config.yaml")
        self.logger = logging.getLogger(__name__)

    async def execute(self) -> None:
        if not self._is_kill_zone():
            self.logger.info("Outside Kill Zone, skipping")
            return

        try:
            # Получение данных в зависимости от режима
            if self.global_config["mode"] == "backtest":
                data = self.data_feed.get_data(self.symbol, self.timeframe)
            else:
                data = await self.data_feed.get_data(self.symbol, self.timeframe)
                
            if data.empty:
                self.logger.warning("No data received")
                return

            daily_bias = self._get_daily_bias()
            ms_break = self._detect_market_structure_break(data)
            judas_swing = self._detect_judas_swing(data)
            ote = self._detect_optimal_trade_entry(data)

            if ms_break and daily_bias == ms_break["type"]:
                await self._trade_market_structure(ms_break, data)
            if judas_swing and daily_bias == judas_swing["type"]:
                await self._trade_judas_swing(judas_swing, data)
            if ote and daily_bias == ote["type"]:
                await self._trade_optimal_trade_entry(ote, data)

        except Exception as e:
            self.logger.error(f"ICT strategy error: {e}")

    def _is_kill_zone(self) -> bool:
        now = datetime.utcnow().time()
        sessions = {
            "london": (time(8, 0), time(11, 0)),
            "new_york": (time(13, 0), time(16, 0))
        }
        for session, (start, end) in sessions.items():
            if start <= now <= end and self.config["kill_zones"][session]:
                return True
        return False

    def _get_daily_bias(self) -> str:
        if self.global_config["mode"] == "backtest":
            daily_data = self.data_feed.get_data(self.symbol, "DAY", 10)
        else:
            daily_data = asyncio.run(self.data_feed.get_data(self.symbol, "DAY", 10))
        if daily_data.empty:
            return "neutral"
        return "bullish" if daily_data["close"].iloc[-1] > daily_data["open"].iloc[-1] else "bearish"

    def _detect_market_structure_break(self, data: pd.DataFrame) -> Optional[Dict]:
        # Создаём копию DataFrame, чтобы избежать SettingWithCopyWarning
        df = data.copy()
        
        # Рассчёт индикаторов
        df["higher_high"] = df["high"] > df["high"].shift(1)
        df["lower_low"] = df["low"] < df["low"].shift(1)
        last_candle = df.iloc[-1]
        
        if last_candle["higher_high"] and df["close"].iloc[-1] > df["high"].iloc[-2]:
            return {"price": last_candle["close"], "type": "bullish"}
        elif last_candle["lower_low"] and df["close"].iloc[-1] < df["low"].iloc[-2]:
            return {"price": last_candle["close"], "type": "bearish"}
        return None

    def _detect_judas_swing(self, data: pd.DataFrame) -> Optional[Dict]:
        recent_high = data["high"].iloc[-10:].max()
        recent_low = data["low"].iloc[-10:].min()
        last_candle = data.iloc[-1]
        if last_candle["high"] > recent_high and last_candle["close"] < recent_high:
            return {"price": last_candle["close"], "type": "bearish"}
        elif last_candle["low"] < recent_low and last_candle["close"] > recent_low:
            return {"price": last_candle["close"], "type": "bullish"}
        return None

    def _detect_optimal_trade_entry(self, data: pd.DataFrame) -> Optional[Dict]:
        swing_high = data["high"].iloc[-20:].max()
        swing_low = data["low"].iloc[-20:].min()
        fib_618 = swing_low + (swing_high - swing_low) * 0.618
        fib_786 = swing_low + (swing_high - swing_low) * 0.786
        last_candle = data.iloc[-1]
        if fib_618 <= last_candle["close"] <= fib_786:
            return {"price": last_candle["close"], "type": "bullish"}
        elif swing_high - (swing_high - swing_low) * 0.786 <= last_candle["close"] <= swing_high - (swing_high - swing_low) * 0.618:
            return {"price": last_candle["close"], "type": "bearish"}
        return None

    async def _trade_market_structure(self, ms_break: Dict, data: pd.DataFrame) -> None:
        direction = "BUY" if ms_break["type"] == "bullish" else "SELL"
        sl, tp = self.sl_tp_calculator.calculate_sl_tp(data, ms_break["price"], direction)
        size = self.risk_manager.calculate_position_size(ms_break["price"], sl)
        await self.order_manager.place_order(self.symbol, direction, size, ms_break["price"], sl, tp)

    async def _trade_judas_swing(self, judas: Dict, data: pd.DataFrame) -> None:
        direction = "BUY" if judas["type"] == "bullish" else "SELL"
        sl, tp = self.sl_tp_calculator.calculate_sl_tp(data, judas["price"], direction)
        size = self.risk_manager.calculate_position_size(judas["price"], sl)
        await self.order_manager.place_order(self.symbol, direction, size, judas["price"], sl, tp)

    async def _trade_optimal_trade_entry(self, ote: Dict, data: pd.DataFrame) -> None:
        direction = "BUY" if ote["type"] == "bullish" else "SELL"
        sl, tp = self.sl_tp_calculator.calculate_sl_tp(data, ote["price"], direction)
        size = self.risk_manager.calculate_position_size(ote["price"], sl)
        await self.order_manager.place_order(self.symbol, direction, size, ote["price"], sl, tp)