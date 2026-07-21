from .base import Action, BaseStrategy, Signal
from .indicators import macd


class MomentumBreakoutStrategy(BaseStrategy):
    name = "momentum_breakout"

    def generate_signal(self, symbol: str, candles: list[dict]) -> Signal:
        closes = [c["close"] for c in candles]
        volumes = [c["volume"] for c in candles]
        if len(closes) < 27:
            return Signal(Action.HOLD, symbol)

        macd_line, signal_line = macd(closes)
        avg_volume = sum(volumes[-20:]) / 20
        curr_volume = volumes[-1]

        prev_macd, prev_signal = macd_line.iloc[-2], signal_line.iloc[-2]
        curr_macd, curr_signal = macd_line.iloc[-1], signal_line.iloc[-1]
        volume_confirmed = curr_volume > avg_volume

        if prev_macd <= prev_signal and curr_macd > curr_signal and volume_confirmed:
            return Signal(Action.BUY, symbol)
        if prev_macd >= prev_signal and curr_macd < curr_signal:
            return Signal(Action.SELL, symbol)
        return Signal(Action.HOLD, symbol)
