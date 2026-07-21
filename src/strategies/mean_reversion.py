from .base import Action, BaseStrategy, Signal
from .indicators import bollinger_bands, rsi


class MeanReversionStrategy(BaseStrategy):
    name = "mean_reversion"

    def generate_signal(self, symbol: str, candles: list[dict]) -> Signal:
        closes = [c["close"] for c in candles]
        if len(closes) < 21:
            return Signal(Action.HOLD, symbol)

        rsi_values = rsi(closes, 14)
        upper, _, lower = bollinger_bands(closes, 20, 2.0)

        curr_rsi = rsi_values.iloc[-1]
        curr_close = closes[-1]

        if curr_rsi < 30 and curr_close <= lower.iloc[-1]:
            return Signal(Action.BUY, symbol)
        if curr_rsi > 70 and curr_close >= upper.iloc[-1]:
            return Signal(Action.SELL, symbol)
        return Signal(Action.HOLD, symbol)
