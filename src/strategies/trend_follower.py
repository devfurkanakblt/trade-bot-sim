from .base import Action, BaseStrategy, Signal
from .indicators import ema


class TrendFollowerStrategy(BaseStrategy):
    name = "trend_follower"

    def generate_signal(self, symbol: str, candles: list[dict]) -> Signal:
        closes = [c["close"] for c in candles]
        if len(closes) < 22:
            return Signal(Action.HOLD, symbol)

        ema_fast = ema(closes, 9)
        ema_slow = ema(closes, 21)
        prev_fast, prev_slow = ema_fast.iloc[-2], ema_slow.iloc[-2]
        curr_fast, curr_slow = ema_fast.iloc[-1], ema_slow.iloc[-1]

        if prev_fast <= prev_slow and curr_fast > curr_slow:
            return Signal(Action.BUY, symbol)
        if prev_fast >= prev_slow and curr_fast < curr_slow:
            return Signal(Action.SELL, symbol)
        return Signal(Action.HOLD, symbol)
