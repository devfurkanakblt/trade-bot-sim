from .base import Action, BaseStrategy, Signal


class GridTraderStrategy(BaseStrategy):
    name = "grid_trader"

    def __init__(self, grid_step_pct: float = 0.02):
        self.grid_step_pct = grid_step_pct
        self.reference_price: dict[str, float] = {}
        self.last_level: dict[str, int] = {}

    def generate_signal(self, symbol: str, candles: list[dict]) -> Signal:
        if not candles:
            return Signal(Action.HOLD, symbol)
        price = candles[-1]["close"]

        if symbol not in self.reference_price:
            self.reference_price[symbol] = price
            self.last_level[symbol] = 0
            return Signal(Action.HOLD, symbol)

        ref = self.reference_price[symbol]
        current_level = round((price - ref) / (ref * self.grid_step_pct))
        prev_level = self.last_level[symbol]
        self.last_level[symbol] = current_level

        if current_level < prev_level:
            return Signal(Action.BUY, symbol)
        if current_level > prev_level:
            return Signal(Action.SELL, symbol)
        return Signal(Action.HOLD, symbol)
