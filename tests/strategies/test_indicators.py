import pytest

from src.strategies.indicators import bollinger_bands, ema, macd, rsi


def test_ema_of_constant_series_equals_constant():
    result = ema([10.0] * 5, period=3)
    assert result.iloc[-1] == pytest.approx(10.0)


def test_ema_reacts_to_recent_values():
    result = ema([10.0] * 10 + [20.0] * 5, period=3)
    assert result.iloc[-1] > 10.0
    assert result.iloc[-1] < 20.0


def test_rsi_of_strictly_increasing_series_is_high():
    values = [float(i) for i in range(1, 30)]
    result = rsi(values, period=14)
    assert result.iloc[-1] > 90


def test_rsi_of_strictly_decreasing_series_is_low():
    values = [float(i) for i in range(30, 1, -1)]
    result = rsi(values, period=14)
    assert result.iloc[-1] < 10


def test_rsi_of_flat_price_series_is_neutral():
    values = [100.0] * 30
    result = rsi(values, period=14)
    assert result.iloc[-1] == pytest.approx(50.0)


def test_bollinger_bands_mid_equals_rolling_mean():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    upper, mid, lower = bollinger_bands(values, period=5, num_std=2.0)
    assert mid.iloc[-1] == pytest.approx(3.0)
    assert upper.iloc[-1] > mid.iloc[-1]
    assert lower.iloc[-1] < mid.iloc[-1]


def test_macd_line_is_difference_of_emas():
    values = [float(i) for i in range(1, 40)]
    macd_line, signal_line = macd(values, fast=5, slow=10, signal=3)
    expected = ema(values, 5).iloc[-1] - ema(values, 10).iloc[-1]
    assert macd_line.iloc[-1] == pytest.approx(expected)
    assert len(signal_line) == len(macd_line)
