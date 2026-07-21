import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    def __init__(self):
        self.WATCHLIST = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
        self.INITIAL_BALANCE = 10_000.0
        self.DB_PATH = os.getenv("DB_PATH", "trade_bot_sim.db")
        self.PUSHBULLET_TOKEN = os.getenv("PUSHBULLET_TOKEN", "")
        self.TIMEZONE = "Europe/Istanbul"
