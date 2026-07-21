import time

from src.strategies.base import Action
from src.strategies.ml_predictor import MLPredictorStrategy


def make_trending_candles(n: int, start: float = 100.0, step: float = 1.0) -> list[dict]:
    closes = [start + i * step for i in range(n)]
    # Add one final candle with a dip to create target=0 for model training
    # This ensures we have both classes (0 and 1) for training the classifier
    if len(closes) > 1:
        closes.append(closes[-1] - step * 2)
    return [
        {"close": c, "open": c, "high": c + 0.5, "low": c - 0.5, "volume": 10.0 + i % 5, "open_time": i}
        for i, c in enumerate(closes)
    ]


def test_not_enough_data_returns_hold():
    strategy = MLPredictorStrategy()
    signal = strategy.generate_signal("BTCUSDT", make_trending_candles(10))
    assert signal.action == Action.HOLD


def test_trains_model_on_first_sufficient_call():
    strategy = MLPredictorStrategy()
    candles = make_trending_candles(100)
    strategy.generate_signal("BTCUSDT", candles)
    assert strategy.model is not None


def test_strong_uptrend_produces_buy_with_confidence():
    strategy = MLPredictorStrategy()
    candles = make_trending_candles(100, start=100.0, step=2.0)
    signal = strategy.generate_signal("BTCUSDT", candles)
    assert signal.action == Action.BUY
    assert signal.confidence >= 0.6


def test_does_not_retrain_within_interval(monkeypatch):
    strategy = MLPredictorStrategy()
    candles = make_trending_candles(100)
    strategy.generate_signal("BTCUSDT", candles)
    first_trained_at = strategy.last_trained_at

    monkeypatch.setattr(time, "time", lambda: first_trained_at + 10)
    strategy.generate_signal("BTCUSDT", candles)
    assert strategy.last_trained_at == first_trained_at


def test_retrains_after_interval_elapses(monkeypatch):
    strategy = MLPredictorStrategy()
    candles = make_trending_candles(100)
    strategy.generate_signal("BTCUSDT", candles)
    first_trained_at = strategy.last_trained_at

    monkeypatch.setattr(time, "time", lambda: first_trained_at + 8 * 24 * 3600)
    strategy.generate_signal("BTCUSDT", candles)
    assert strategy.last_trained_at > first_trained_at
