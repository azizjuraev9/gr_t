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
            df["close"] = df["closePrice"].apply(lambda x: x.get("bid") if isinstance(x, dict) else None)
            df["open"] = df["openPrice"].apply(lambda x: x.get("bid") if isinstance(x, dict) else None)
            df["high"] = df["highPrice"].apply(lambda x: x.get("bid") if isinstance(x, dict) else None)
            df["low"] = df["lowPrice"].apply(lambda x: x.get("bid") if isinstance(x, dict) else None)
            df["volume"] = df["lastTradedVolume"]

            return df[["timestamp", "open", "high", "low", "close", "volume"]]
        except Exception as e:
            self.logger.error(f"Failed to fetch data: {e}")
            return pd.DataFrame()