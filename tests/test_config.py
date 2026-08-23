from src.config import Config


def test_config_has_kline_interval_and_web_port():
    config = Config()
    assert config.KLINE_INTERVAL == "1m"
    assert config.WEB_PORT == 8000


def test_config_defaults(monkeypatch):
    monkeypatch.delenv("DB_PATH", raising=False)
    monkeypatch.delenv("PUSHBULLET_TOKEN", raising=False)
    monkeypatch.delenv("MARKET_DATA_BASE_URL", raising=False)
    monkeypatch.delenv("PUSHBULLET_API_URL", raising=False)
    monkeypatch.delenv("OUTBOUND_PROXY_TOKEN", raising=False)
    config = Config()
    assert config.WATCHLIST == ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
    assert config.INITIAL_BALANCE == 10_000.0
    assert config.DB_PATH == "trade_bot_sim.db"
    assert config.TIMEZONE == "Europe/Istanbul"
    assert config.MARKET_UNIVERSE_SIZE == 50
    assert config.MARKET_DATA_BASE_URL == "https://data-api.binance.vision"
    assert config.PUSHBULLET_API_URL == "https://api.pushbullet.com/v2/pushes"
    assert config.OUTBOUND_PROXY_TOKEN == ""


def test_config_env_override(monkeypatch):
    monkeypatch.setenv("DB_PATH", "/tmp/custom.db")
    monkeypatch.setenv("PUSHBULLET_TOKEN", "abc123")
    monkeypatch.setenv("MARKET_DATA_BASE_URL", "https://worker.example/binance/")
    monkeypatch.setenv("PUSHBULLET_API_URL", "https://worker.example/pushbullet/v2/pushes")
    monkeypatch.setenv("OUTBOUND_PROXY_TOKEN", "proxy-secret")
    config = Config()
    assert config.DB_PATH == "/tmp/custom.db"
    assert config.PUSHBULLET_TOKEN == "abc123"
    assert config.MARKET_DATA_BASE_URL == "https://worker.example/binance"
    assert config.PUSHBULLET_API_URL == "https://worker.example/pushbullet/v2/pushes"
    assert config.OUTBOUND_PROXY_TOKEN == "proxy-secret"


def test_proxy_configuration_requires_token_and_both_custom_urls(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_BASE_URL", "https://worker.example/binance")
    monkeypatch.delenv("OUTBOUND_PROXY_TOKEN", raising=False)

    import pytest

    with pytest.raises(ValueError, match="require OUTBOUND_PROXY_TOKEN"):
        Config()
