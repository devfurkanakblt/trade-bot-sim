from src.strategies.base import Action
from src.strategies.mean_reversion import MeanReversionStrategy


def make_candles(closes: list[float]) -> list[dict]:
    return [{"close": c, "open": c, "high": c, "low": c, "volume": 1.0, "open_time": i} for i, c in enumerate(closes)]


def test_not_enough_data_returns_hold():
    strategy = MeanReversionStrategy()
    signal = strategy.generate_signal("BTCUSDT", make_candles([100.0] * 5))
    assert signal.action == Action.HOLD


def test_oversold_dip_returns_buy():
    closes = [100.0] * 20 + [90.0, 80.0, 70.0]
    strategy = MeanReversionStrategy()
    signal = strategy.generate_signal("BTCUSDT", make_candles(closes))
    assert signal.action == Action.BUY


def test_overbought_spike_returns_sell():
    closes = [100.0] * 20 + [110.0, 120.0, 130.0]
    strategy = MeanReversionStrategy()
    signal = strategy.generate_signal("BTCUSDT", make_candles(closes))
    assert signal.action == Action.SELL


def test_stable_series_returns_hold():
    strategy = MeanReversionStrategy()
    signal = strategy.generate_signal("BTCUSDT", make_candles([100.0] * 25))
    assert signal.action == Action.HOLD
