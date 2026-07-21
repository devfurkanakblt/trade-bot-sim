from dataclasses import dataclass
from enum import Enum


class Action(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class Signal:
    action: Action
    symbol: str
    confidence: float = 1.0


class BaseStrategy:
    name: str = "base"

    def generate_signal(self, symbol: str, candles: list[dict]) -> Signal:
        raise NotImplementedError
