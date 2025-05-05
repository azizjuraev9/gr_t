import pandas as pd
import logging
from typing import Optional, Dict, List
from src.data_feed import DataFeed
from src.order_manager import OrderManager
from src.risk_manager import RiskManager
from src.stop_loss_take_profit import StopLossTakeProfit
from src.early_exit import EarlyExit
from src.config import load_config

class SMCStrategy:
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
        try:
            # Получение данных в зависимости от режима
            if self.global_config["mode"] == "backtest":
                data = self.data_feed.get_data(self.symbol, self.timeframe)
            else:
                data = await self.data_feed.get_data(self.symbol, self.timeframe)
                
            if data.empty:
                self.logger.warning("No data received")
                return

            order_block = self._detect_order_block(data)
            fvg = self._detect_fair_value_gap(data)
            liquidity = self._detect_liquidity_grab(data)
            bos = self._detect_break_of_structure(data)
            choch = self._detect_change_of_character(data)

            if order_block:
                await self._trade_order_block(order_block, data)
            if fvg:
                await self._trade_fair_value_gap(fvg, data)
            if liquidity:
                await self._trade_liquidity_grab(liquidity, data)
            if bos:
                await self._trade_break_of_structure(bos, data)
            if choch:
                await self._trade_change_of_character(choch, data)

        except Exception as e:
            self.logger.error(f"SMC strategy error: {e}")

    def _detect_order_block(self, data: pd.DataFrame) -> Optional[Dict]:
        data = data.copy()
        data["range"] = data["high"] - data["low"]
        data["is_bullish"] = data["close"] > data["open"]
        last_candle = data.iloc[-1]
        prev_candle = data.iloc[-2]
        if (last_candle["volume"] > data["volume"].mean() * self.config["ob_volume_multiplier"] and
                last_candle["range"] > data["range"].mean() and
                prev_candle["is_bullish"] != last_candle["is_bullish"]):
            return {
                "price": last_candle["close"],
                "type": "bullish" if last_candle["is_bullish"] else "bearish",
                "high": last_candle["high"],
                "low": last_candle["low"]
            }
        return None

    def _detect_fair_value_gap(self, data: pd.DataFrame) -> Optional[Dict]:
        for i in range(len(data) - 2):
            c1 = data.iloc[i]
            c2 = data.iloc[i+1]
            c3 = data.iloc[i+2]
            if c1["high"] < c3["low"] and c2["close"] > c2["open"]:
                return {"price": (c1["high"] + c3["low"]) / 2, "type": "bullish"}
            elif c1["low"] > c3["high"] and c2["close"] < c2["open"]:
                return {"price": (c1["low"] + c3["high"]) / 2, "type": "bearish"}
        return None

    def _detect_liquidity_grab(self, data: pd.DataFrame) -> Optional[Dict]:
        recent_high = data["high"].iloc[-10:].max()
        recent_low = data["low"].iloc[-10:].min()
        last_candle = data.iloc[-1]
        if last_candle["high"] > recent_high:
            return {"price": recent_high, "type": "bearish"}
        elif last_candle["low"] < recent_low:
            return {"price": recent_low, "type": "bullish"}
        return None

    def _detect_break_of_structure(self, data: pd.DataFrame) -> Optional[Dict]:
        data = data.copy()
        data["higher_high"] = data["high"] > data["high"].shift(1)
        data["lower_low"] = data["low"] < data["low"].shift(1)
        last_candle = data.iloc[-1]
        if last_candle["higher_high"] and data["close"].iloc[-1] > data["high"].iloc[-2]:
            return {"price": last_candle["close"], "type": "bullish"}
        elif last_candle["lower_low"] and data["close"].iloc[-1] < data["low"].iloc[-2]:
            return {"price": last_candle["close"], "type": "bearish"}
        return None

    def _detect_change_of_character(self, data: pd.DataFrame) -> Optional[Dict]:
        data = data.copy()
        data["trend"] = data["close"].rolling(20).mean()
        last_candle = data.iloc[-1]
        if last_candle["close"] > data["trend"].iloc[-1] and data["close"].iloc[-2] < data["trend"].iloc[-2]:
            return {"price": last_candle["close"], "type": "bullish"}
        elif last_candle["close"] < data["trend"].iloc[-1] and data["close"].iloc[-2] > data["trend"].iloc[-2]:
            return {"price": last_candle["close"], "type": "bearish"}
        return None

    async def _trade_order_block(self, ob: Dict, data: pd.DataFrame) -> None:
        direction = "BUY" if ob["type"] == "bullish" else "SELL"
        sl, tp = self.sl_tp_calculator.calculate_sl_tp(data, ob["price"], direction)
        size = self.risk_manager.calculate_position_size(ob["price"], sl)

        if size == 0.0:
            return

        await self.order_manager.place_order(self.symbol, direction, size, ob["price"], sl, tp)

    async def _trade_fair_value_gap(self, fvg: Dict, data: pd.DataFrame) -> None:
        direction = "BUY" if fvg["type"] == "bullish" else "SELL"
        sl, tp = self.sl_tp_calculator.calculate_sl_tp(data, fvg["price"], direction)
        size = self.risk_manager.calculate_position_size(fvg["price"], sl)

        if size == 0.0:
            return

        await self.order_manager.place_order(self.symbol, direction, size, fvg["price"], sl, tp)

    async def _trade_liquidity_grab(self, liquidity: Dict, data: pd.DataFrame) -> None:
        direction = "BUY" if liquidity["type"] == "bullish" else "SELL"
        sl, tp = self.sl_tp_calculator.calculate_sl_tp(data, liquidity["price"], direction)
        size = self.risk_manager.calculate_position_size(liquidity["price"], sl)

        if size == 0.0:
            return

        await self.order_manager.place_order(self.symbol, direction, size, liquidity["price"], sl, tp)

    async def _trade_break_of_structure(self, bos: Dict, data: pd.DataFrame) -> None:
        direction = "BUY" if bos["type"] == "bullish" else "SELL"
        sl, tp = self.sl_tp_calculator.calculate_sl_tp(data, bos["price"], direction)
        size = self.risk_manager.calculate_position_size(bos["price"], sl)

        if size == 0.0:
            return

        await self.order_manager.place_order(self.symbol, direction, size, bos["price"], sl, tp)

    async def _trade_change_of_character(self, choch: Dict, data: pd.DataFrame) -> None:
        direction = "BUY" if choch["type"] == "bullish" else "SELL"
        sl, tp = self.sl_tp_calculator.calculate_sl_tp(data, choch["price"], direction)
        size = self.risk_manager.calculate_position_size(choch["price"], sl)

        if size == 0.0:
            return

        await self.order_manager.place_order(self.symbol, direction, size, choch["price"], sl, tp)