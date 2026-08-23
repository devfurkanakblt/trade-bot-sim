from .base import Action, BaseStrategy, Signal
from .indicators import ema


class ScalperStrategy(BaseStrategy):
    """Fast EMA crossover strategy with a small volume confirmation filter."""

    name = "scalper"

    def generate_signal(self, symbol: str, candles: list[dict]) -> Signal:
        closes = [c["close"] for c in candles]
        volumes = [c["volume"] for c in candles]
        if len(closes) < 16:
            return Signal(Action.HOLD, symbol)

        fast = ema(closes, 5)
        slow = ema(closes, 13)
        average_volume = sum(volumes[-10:]) / 10
        crossed_up = fast.iloc[-2] <= slow.iloc[-2] and fast.iloc[-1] > slow.iloc[-1]
        crossed_down = fast.iloc[-2] >= slow.iloc[-2] and fast.iloc[-1] < slow.iloc[-1]

        if crossed_up and volumes[-1] >= average_volume:
            return Signal(Action.BUY, symbol, confidence=0.7)
        if crossed_down:
            return Signal(Action.SELL, symbol, confidence=0.7)
        return Signal(Action.HOLD, symbol)


class LeveragedScalperStrategy(ScalperStrategy):
    """The same fast signal logic, executed by an isolated-margin portfolio."""

    name = "leveraged_scalper"
