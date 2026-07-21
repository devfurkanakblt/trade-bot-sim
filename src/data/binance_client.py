import time

import requests

BASE_URL = "https://api.binance.com"


class MarketDataError(Exception):
    pass


class MarketDataClient:
    def __init__(self, base_url: str = BASE_URL, max_retries: int = 3, retry_delay_seconds: float = 2.0):
        self.base_url = base_url
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds

    def _get(self, path: str, params: dict):
        last_exc = None
        for _ in range(self.max_retries):
            try:
                resp = requests.get(f"{self.base_url}{path}", params=params, timeout=10)
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(self.retry_delay_seconds)
        raise MarketDataError(f"Failed to fetch {path} after {self.max_retries} attempts: {last_exc}")

    def get_klines(self, symbol: str, interval: str = "1h", limit: int = 100) -> list[dict]:
        raw = self._get("/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit})
        return [
            {
                "open_time": row[0],
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            }
            for row in raw
        ]

    def get_current_price(self, symbol: str) -> float:
        raw = self._get("/api/v3/ticker/price", {"symbol": symbol})
        return float(raw["price"])
