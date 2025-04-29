import pandas as pd
import logging
from typing import List, Dict
from src.client import CapitalClient

class DataFeed:
    def __init__(self, client: CapitalClient):
        self.client = client
        self.logger = logging.getLogger(__name__)

    async def get_data(self, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        try:
            raw_data = self.client.get_market_data(symbol, timeframe, limit)
            if not raw_data:
                return pd.DataFrame()

            df = pd.DataFrame(raw_data)
            df["timestamp"] = pd.to_datetime(df["snapshotTimeUTC"])
            df["open"] = df["openPrice"]["bid"]
            df["high"] = df["highPrice"]["bid"]
            df["low"] = df["lowPrice"]["bid"]
            df["close"] = df["closePrice"]["bid"]
            df["volume"] = df.get("volume", 0)
            return df[["timestamp", "open", "high", "low", "close", "volume"]]
        except Exception as e:
            self.logger.error(f"Failed to fetch data: {e}")
            return pd.DataFrame()