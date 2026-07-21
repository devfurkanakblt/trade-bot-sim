from src.config import Config


def test_config_defaults(monkeypatch):
    monkeypatch.delenv("DB_PATH", raising=False)
    monkeypatch.delenv("PUSHBULLET_TOKEN", raising=False)
    config = Config()
    assert config.WATCHLIST == ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
    assert config.INITIAL_BALANCE == 10_000.0
    assert config.DB_PATH == "trade_bot_sim.db"
    assert config.TIMEZONE == "Europe/Istanbul"


def test_config_env_override(monkeypatch):
    monkeypatch.setenv("DB_PATH", "/tmp/custom.db")
    monkeypatch.setenv("PUSHBULLET_TOKEN", "abc123")
    config = Config()
    assert config.DB_PATH == "/tmp/custom.db"
    assert config.PUSHBULLET_TOKEN == "abc123"
