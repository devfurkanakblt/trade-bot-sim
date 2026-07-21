from src.strategies.base import Action
from src.strategies.trend_follower import TrendFollowerStrategy


def make_candles(closes: list[float]) -> list[dict]:
    return [{"close": c, "open": c, "high": c, "low": c, "volume": 1.0, "open_time": i} for i, c in enumerate(closes)]


def test_not_enough_data_returns_hold():
    strategy = TrendFollowerStrategy()
    signal = strategy.generate_signal("BTCUSDT", make_candles([100.0] * 5))
    assert signal.action == Action.HOLD


def test_bullish_crossover_returns_buy():
    # Flat then a sharp recent upswing pulls the fast EMA above the slow EMA
    closes = [100.0] * 29 + [140.0]
    strategy = TrendFollowerStrategy()
    signal = strategy.generate_signal("BTCUSDT", make_candles(closes))
    assert signal.action == Action.BUY
    assert signal.symbol == "BTCUSDT"


def test_bearish_crossover_returns_sell():
    closes = [100.0] * 29 + [60.0]
    strategy = TrendFollowerStrategy()
    signal = strategy.generate_signal("BTCUSDT", make_candles(closes))
    assert signal.action == Action.SELL


def test_flat_series_returns_hold():
    strategy = TrendFollowerStrategy()
    signal = strategy.generate_signal("BTCUSDT", make_candles([100.0] * 30))
    assert signal.action == Action.HOLD
