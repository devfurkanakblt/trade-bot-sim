import pytest

from src.strategies.base import BaseStrategy


def test_base_strategy_raises_not_implemented():
    strategy = BaseStrategy()
    with pytest.raises(NotImplementedError):
        strategy.generate_signal("BTCUSDT", [])
