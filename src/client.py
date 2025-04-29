import requests
import logging
from typing import Dict, List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

class CapitalClient:
    def __init__(self, api_key: str, api_secret: str, account_id: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.account_id = account_id
        self.base_url = "https://demo-api-capital.backend-capital.com/api/v1"
        self.session = requests.Session()
        self.session.headers.update({"X-CAP-API-KEY": self.api_key})
        self.logger = logging.getLogger(__name__)
        self._authenticate()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _authenticate(self) -> None:
        try:
            response = self.session.post(
                f"{self.base_url}/session",
                json={
                    "identifier": self.account_id, 
                    "password": self.api_secret,
                    "encryptedPassword": False
                }
            )
            response.raise_for_status()
            self.session.headers.update({"CST": response.headers.get("CST")})
            self.logger.info("Authenticated successfully")
        except Exception as e:
            self.logger.error(f"Authentication failed: {e}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def get_market_data(self, symbol: str, timeframe: str, limit: int = 100) -> List[Dict]:
        try:
            response = self.session.get(
                f"{self.base_url}/prices",
                params={"epic": symbol, "resolution": timeframe, "max": limit}
            )
            response.raise_for_status()
            return response.json().get("prices", [])
        except Exception as e:
            self.logger.error(f"Failed to fetch market data: {e}")
            return []

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def place_order(self, symbol: str, direction: str, size: float, price: Optional[float] = None,
                    stop_loss: Optional[float] = None, take_profit: Optional[float] = None) -> Dict:
        try:
            payload = {
                "epic": symbol,
                "direction": direction.upper(),
                "size": size,
                "price": price,
                "stopLevel": stop_loss,
                "profitLevel": take_profit
            }
            response = self.session.post(f"{self.base_url}/positions", json=payload)
            response.raise_for_status()
            self.logger.info(f"Order placed: {payload}")
            return response.json()
        except Exception as e:
            self.logger.error(f"Failed to place order: {e}")
            return {}

    def get_account_balance(self) -> float:
        try:
            response = self.session.get(f"{self.base_url}/accounts/{self.account_id}")
            response.raise_for_status()
            return response.json().get("balance", {}).get("available", 0.0)
        except Exception as e:
            self.logger.error(f"Failed to fetch balance: {e}")
            return 0.0