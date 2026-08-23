import time

import requests

BASE_URL = "https://data-api.binance.vision"


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
        try:
            now_ms = int(time.time() * 1000)
            candles = [
                {
                    "open_time": row[0],
                    "close_time": row[6],
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                }
                for row in raw
            ]
            # Binance includes the currently-forming kline as the final row.
            # Strategy signals must only use completed candles so results are
            # reproducible and do not change several times within one minute.
            return [candle for candle in candles if candle["close_time"] <= now_ms]
        except (KeyError, TypeError, IndexError, ValueError) as exc:
            raise MarketDataError(
                f"Failed to parse klines response for {symbol}: {exc.__class__.__name__}: {exc}"
            )

    def get_current_price(self, symbol: str) -> float:
        raw = self._get("/api/v3/ticker/price", {"symbol": symbol})
        try:
            return float(raw["price"])
        except (KeyError, TypeError, ValueError) as exc:
            raise MarketDataError(
                f"Failed to parse price response for {symbol}: {exc.__class__.__name__}: {exc}"
            )

    def get_popular_usdt_pairs(self, limit: int = 50) -> list[str]:
        """Return liquid, tradable USDT spot pairs ranked by 24h quote volume.

        ``limit=0`` deliberately means every eligible market. Leveraged-token
        pairs are excluded because their own embedded leverage would make them
        unsuitable for a paper-futures strategy.
        """
        raw = self._get("/api/v3/ticker/24hr", {})
        try:
            pairs = []
            excluded_suffixes = ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT")
            for ticker in raw:
                symbol = ticker["symbol"]
                if not symbol.endswith("USDT") or symbol.endswith(excluded_suffixes):
                    continue
                quote_volume = float(ticker["quoteVolume"])
                if quote_volume > 0:
                    pairs.append((symbol, quote_volume))
            pairs.sort(key=lambda item: item[1], reverse=True)
            symbols = [symbol for symbol, _ in pairs]
            return symbols if limit <= 0 else symbols[:limit]
        except (KeyError, TypeError, ValueError) as exc:
            raise MarketDataError(
                f"Failed to parse 24h ticker response: {exc.__class__.__name__}: {exc}"
            )
