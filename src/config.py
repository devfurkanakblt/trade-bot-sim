import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    def __init__(self):
        # This small, known-good list is only used while the market-universe
        # endpoint is unavailable. Normal operation dynamically selects the
        # highest-volume USDT markets instead of restricting agents to four
        # manually maintained pairs.
        self.WATCHLIST = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
        self.MARKET_UNIVERSE_SIZE = int(os.getenv("MARKET_UNIVERSE_SIZE", "50"))
        self.MARKET_UNIVERSE_REFRESH_SECONDS = int(
            os.getenv("MARKET_UNIVERSE_REFRESH_SECONDS", "900")
        )
        self.INITIAL_BALANCE = 10_000.0
        self.DB_PATH = os.getenv("DB_PATH", "trade_bot_sim.db")
        self.PUSHBULLET_TOKEN = os.getenv("PUSHBULLET_TOKEN", "")
        self.MARKET_DATA_BASE_URL = os.getenv(
            "MARKET_DATA_BASE_URL", "https://data-api.binance.vision"
        ).rstrip("/")
        self.PUSHBULLET_API_URL = os.getenv(
            "PUSHBULLET_API_URL", "https://api.pushbullet.com/v2/pushes"
        )
        self.OUTBOUND_PROXY_TOKEN = os.getenv("OUTBOUND_PROXY_TOKEN", "")
        official_market_url = "https://data-api.binance.vision"
        official_pushbullet_url = "https://api.pushbullet.com/v2/pushes"
        custom_market_url = self.MARKET_DATA_BASE_URL != official_market_url
        custom_pushbullet_url = self.PUSHBULLET_API_URL != official_pushbullet_url
        if self.OUTBOUND_PROXY_TOKEN and not (custom_market_url and custom_pushbullet_url):
            raise ValueError(
                "OUTBOUND_PROXY_TOKEN requires both API URLs to use the authenticated proxy"
            )
        if (custom_market_url or custom_pushbullet_url) and not self.OUTBOUND_PROXY_TOKEN:
            raise ValueError("Custom API URLs require OUTBOUND_PROXY_TOKEN")
        self.TIMEZONE = "Europe/Istanbul"
        # One-minute candles let the scalping agents react quickly while the
        # scheduler remains the single source of tick cadence.
        self.KLINE_INTERVAL = os.getenv("KLINE_INTERVAL", "1m")
        self.WEB_PORT = int(os.getenv("WEB_PORT", "8000"))
