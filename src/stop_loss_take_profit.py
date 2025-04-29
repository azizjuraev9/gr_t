import pandas as pd
import logging
from typing import Tuple, Optional

class StopLossTakeProfit:
    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(__name__)

    def calculate_sl_tp(self, data: pd.DataFrame, entry_price: float, direction: str) -> Tuple[float, float]:
        """Расчёт оптимальных SL и TP."""
        try:
            # Рассчёт ATR
            atr = self._calculate_atr(data)
            atr_multiplier_sl = self.config["atr_multiplier_sl"]
            atr_multiplier_tp = self.config["atr_multiplier_tp"]

            # Определение уровней поддержки/сопротивления
            support, resistance = self._find_support_resistance(data)

            # Базовый SL и TP на основе ATR
            if direction.upper() == "BUY":
                sl = entry_price - atr * atr_multiplier_sl
                tp = entry_price + atr * atr_multiplier_tp * self.config["rr_ratio"]
                # Корректировка SL/TP с учётом уровней
                sl = max(sl, support * 0.995) if support else sl
                tp = min(tp, resistance * 1.005) if resistance else tp
            else:  # SELL
                sl = entry_price + atr * atr_multiplier_sl
                tp = entry_price - atr * atr_multiplier_tp * self.config["rr_ratio"]
                sl = min(sl, resistance * 1.005) if resistance else sl
                tp = max(tp, support * 0.995) if support else tp

            self.logger.info(f"Calculated SL: {sl}, TP: {tp} for entry {entry_price}")
            return round(sl, 5), round(tp, 5)

        except Exception as e:
            self.logger.error(f"Error calculating SL/TP: {e}")
            return entry_price * 0.995, entry_price * 1.01  # Fallback

    def _calculate_atr(self, data: pd.DataFrame) -> float:
        """Рассчёт ATR (Average True Range)."""
        # Создаём копию DataFrame, чтобы избежать SettingWithCopyWarning
        df = data.copy()
        
        # Рассчёт True Range
        df["high_low"] = df["high"] - df["low"]
        df["high_close"] = abs(df["high"] - df["close"].shift(1))
        df["low_close"] = abs(df["low"] - df["close"].shift(1))
        df["tr"] = df[["high_low", "high_close", "low_close"]].max(axis=1)
        
        # Рассчёт среднего TR
        atr = df["tr"].rolling(self.config["atr_period"]).mean().iloc[-1]
        return atr

    def _find_support_resistance(self, data: pd.DataFrame) -> Tuple[Optional[float], Optional[float]]:
        """Поиск уровней поддержки и сопротивления."""
        window = self.config["sr_window"]
        support = data["low"].rolling(window).min().iloc[-1]
        resistance = data["high"].rolling(window).max().iloc[-1]
        return support, resistance