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
        self.TIMEZONE = "Europe/Istanbul"
        # One-minute candles let the scalping agents react quickly while the
        # scheduler remains the single source of tick cadence.
        self.KLINE_INTERVAL = os.getenv("KLINE_INTERVAL", "1m")
        self.WEB_PORT = int(os.getenv("WEB_PORT", "8000"))
