from dataclasses import dataclass

FEE_RATE = 0.001  # 0.1% simulated Binance spot taker fee


@dataclass
class Position:
    symbol: str
    quantity: float
    avg_entry_price: float


class Portfolio:
    def __init__(self, initial_cash: float):
        self.cash = initial_cash
        self.initial_cash = initial_cash
        self.positions: dict[str, Position] = {}
        self.trade_log: list[dict] = []

    def buy(self, symbol: str, price: float, cash_amount: float) -> dict:
        if cash_amount > self.cash:
            raise ValueError("Insufficient cash")
        fee = cash_amount * FEE_RATE
        net_cash = cash_amount - fee
        quantity = net_cash / price

        self.cash -= cash_amount
        if symbol in self.positions:
            pos = self.positions[symbol]
            total_qty = pos.quantity + quantity
            pos.avg_entry_price = (
                pos.avg_entry_price * pos.quantity + price * quantity
            ) / total_qty
            pos.quantity = total_qty
        else:
            self.positions[symbol] = Position(symbol, quantity, price)

        trade = {
            "side": "BUY",
            "symbol": symbol,
            "price": price,
            "quantity": quantity,
            "fee": fee,
        }
        self.trade_log.append(trade)
        return trade

    def sell(self, symbol: str, price: float, quantity: float) -> dict:
        if symbol not in self.positions or self.positions[symbol].quantity < quantity:
            raise ValueError("Insufficient position")

        pos = self.positions[symbol]
        entry_price = pos.avg_entry_price
        gross = quantity * price
        fee = gross * FEE_RATE
        net = gross - fee
        pnl = (price - entry_price) * quantity - fee

        self.cash += net
        pos.quantity -= quantity
        if pos.quantity <= 1e-12:
            del self.positions[symbol]

        trade = {
            "side": "SELL",
            "symbol": symbol,
            "price": price,
            "quantity": quantity,
            "fee": fee,
            "entry_price": entry_price,
            "pnl": pnl,
        }
        self.trade_log.append(trade)
        return trade

    def total_value(self, current_prices: dict[str, float]) -> float:
        value = self.cash
        for symbol, pos in self.positions.items():
            value += pos.quantity * current_prices.get(symbol, pos.avg_entry_price)
        return value

    def total_pnl(self, current_prices: dict[str, float]) -> tuple[float, float]:
        value = self.total_value(current_prices)
        pnl_abs = value - self.initial_cash
        pnl_pct = (pnl_abs / self.initial_cash) * 100
        return pnl_abs, pnl_pct

    def to_state(self) -> dict:
        return {
            "cash": self.cash,
            "positions": {
                symbol: {
                    "quantity": pos.quantity,
                    "avg_entry_price": pos.avg_entry_price,
                }
                for symbol, pos in self.positions.items()
            },
        }

    @classmethod
    def from_state(cls, initial_cash: float, state: dict) -> "Portfolio":
        portfolio = cls(initial_cash)
        portfolio.cash = state["cash"]
        portfolio.positions = {
            symbol: Position(symbol, data["quantity"], data["avg_entry_price"])
            for symbol, data in state["positions"].items()
        }
        return portfolio
