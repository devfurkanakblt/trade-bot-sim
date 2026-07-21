from src.strategies.base import Action
from src.strategies.momentum_breakout import MomentumBreakoutStrategy


def make_candles(closes: list[float], volumes: list[float]) -> list[dict]:
    return [
        {"close": c, "open": c, "high": c, "low": c, "volume": v, "open_time": i}
        for i, (c, v) in enumerate(zip(closes, volumes))
    ]


def test_not_enough_data_returns_hold():
    strategy = MomentumBreakoutStrategy()
    candles = make_candles([100.0] * 5, [10.0] * 5)
    signal = strategy.generate_signal("BTCUSDT", candles)
    assert signal.action == Action.HOLD


def test_bullish_macd_cross_with_volume_confirmation_returns_buy():
    closes = [100.0] * 32 + [120.0]
    volumes = [10.0] * 32 + [50.0]
    strategy = MomentumBreakoutStrategy()
    signal = strategy.generate_signal("BTCUSDT", make_candles(closes, volumes))
    assert signal.action == Action.BUY


def test_bullish_macd_cross_without_volume_confirmation_returns_hold():
    closes = [100.0] * 32 + [120.0]
    volumes = [10.0] * 33  # no volume spike
    strategy = MomentumBreakoutStrategy()
    signal = strategy.generate_signal("BTCUSDT", make_candles(closes, volumes))
    assert signal.action == Action.HOLD


def test_bearish_macd_cross_returns_sell():
    closes = [100.0] * 32 + [80.0]
    volumes = [10.0] * 33
    strategy = MomentumBreakoutStrategy()
    signal = strategy.generate_signal("BTCUSDT", make_candles(closes, volumes))
    assert signal.action == Action.SELL
