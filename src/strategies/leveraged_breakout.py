from .base import Action, BaseStrategy, Signal


class LeveragedBreakoutStrategy(BaseStrategy):
    """Short-horizon breakout signals intended for the paper-futures agent."""

    name = "leveraged_breakout"

    def generate_signal(self, symbol: str, candles: list[dict]) -> Signal:
        if len(candles) < 21:
            return Signal(Action.HOLD, symbol)

        prior = candles[-21:-1]
        price = candles[-1]["close"]
        high = max(c["high"] for c in prior)
        low = min(c["low"] for c in prior)
        average_volume = sum(c["volume"] for c in prior[-10:]) / 10
        volume_confirmed = candles[-1]["volume"] >= average_volume

        if price > high and volume_confirmed:
            return Signal(Action.BUY, symbol, confidence=0.8)
        if price < low and volume_confirmed:
            return Signal(Action.SELL, symbol, confidence=0.8)
        return Signal(Action.HOLD, symbol)
