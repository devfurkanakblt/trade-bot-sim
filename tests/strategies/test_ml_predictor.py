import time

from src.strategies.base import Action
from src.strategies.ml_predictor import MLPredictorStrategy


def make_regime_candles(
    num_blocks: int = 13,
    block_length: int = 8,
    start: float = 100.0,
    step: float = 1.5,
    volume_base: float = 10.0,
) -> list[dict]:
    """Alternating up/down regime price series.

    Price moves consistently in one direction for `block_length` candles,
    then reverses, repeating for `num_blocks` blocks. This gives the model
    a genuinely learnable relationship between recent momentum
    (return_1 / rsi / macd_diff) and the next candle's direction: within a
    block, the candle-to-candle target matches the block's direction; only
    the single transition candle at the end of each block flips. That
    yields a roughly balanced target class split (not the ~80:1 skew of a
    single monotonic ramp with one dip appended), while still giving the
    classifier a real, majority-of-the-time pattern to learn.

    num_blocks=13 with an initial seed candle and block_length=8 keeps the
    first block direction "up" and, since 13 is odd, the final block is
    also "up" (block indices are 0-based and alternate starting at up) --
    useful for building a genuine uptrend-continuation tail.
    """
    closes = [start]
    direction = 1
    for _ in range(num_blocks):
        for _ in range(block_length):
            closes.append(closes[-1] + direction * step)
        direction *= -1
    return [
        {
            "close": c,
            "open": c,
            "high": c + 0.5,
            "low": c - 0.5,
            "volume": volume_base + (i % 5),
            "open_time": i,
        }
        for i, c in enumerate(closes)
    ]


def test_not_enough_data_returns_hold():
    strategy = MLPredictorStrategy()
    candles = make_regime_candles(num_blocks=1, block_length=8)
    signal = strategy.generate_signal("BTCUSDT", candles)
    assert signal.action == Action.HOLD


def test_trains_model_on_first_sufficient_call():
    strategy = MLPredictorStrategy()
    candles = make_regime_candles()
    strategy.generate_signal("BTCUSDT", candles)
    assert strategy.model is not None


def test_strong_uptrend_produces_buy_with_confidence():
    strategy = MLPredictorStrategy()
    candles = make_regime_candles()
    # Drop the final 2 candles of the last (up) block so the row used for
    # prediction is a genuine interior "still rising" candle -- several
    # real preceding up candles -- rather than the block's reversal
    # transition point or a training-excluded anomaly.
    candles = candles[:-2]
    signal = strategy.generate_signal("BTCUSDT", candles)
    assert signal.action == Action.BUY
    assert signal.confidence >= 0.6


def test_does_not_retrain_within_interval(monkeypatch):
    strategy = MLPredictorStrategy()
    candles = make_regime_candles()
    strategy.generate_signal("BTCUSDT", candles)
    first_trained_at = strategy.last_trained_at

    monkeypatch.setattr(time, "time", lambda: first_trained_at + 10)
    strategy.generate_signal("BTCUSDT", candles)
    assert strategy.last_trained_at == first_trained_at


def test_retrains_after_interval_elapses(monkeypatch):
    strategy = MLPredictorStrategy()
    candles = make_regime_candles()
    strategy.generate_signal("BTCUSDT", candles)
    first_trained_at = strategy.last_trained_at

    monkeypatch.setattr(time, "time", lambda: first_trained_at + 8 * 24 * 3600)
    strategy.generate_signal("BTCUSDT", candles)
    assert strategy.last_trained_at > first_trained_at
