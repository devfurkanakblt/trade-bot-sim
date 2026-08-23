from dataclasses import dataclass

FEE_RATE = 0.001  # 0.1% simulated Binance spot taker fee


@dataclass
class Position:
    symbol: str
    quantity: float
    avg_entry_price: float
    side: str = "LONG"
    leverage: int = 1
    margin: float = 0.0


class Portfolio:
    is_leveraged = False
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
            symbol: Position(
                symbol,
                data["quantity"],
                data["avg_entry_price"],
                data.get("side", "LONG"),
                data.get("leverage", 1),
                data.get("margin", 0.0),
            )
            for symbol, data in state["positions"].items()
        }
        return portfolio


class FuturesPortfolio(Portfolio):
    """Isolated-margin paper futures portfolio supporting long and short trades."""

    is_leveraged = True
    FUTURES_FEE_RATE = 0.0004  # simulated taker fee

    def __init__(self, initial_cash: float, leverage: int = 5):
        super().__init__(initial_cash)
        if leverage < 1:
            raise ValueError("Leverage must be at least 1")
        self.leverage = leverage

    def open_position(self, symbol: str, price: float, margin: float, side: str) -> dict:
        if side not in {"LONG", "SHORT"}:
            raise ValueError("Futures side must be LONG or SHORT")
        if symbol in self.positions:
            raise ValueError("Position already open")
        notional = margin * self.leverage
        fee = notional * self.FUTURES_FEE_RATE
        if margin + fee > self.cash:
            raise ValueError("Insufficient cash for margin")

        quantity = notional / price
        self.cash -= margin + fee
        self.positions[symbol] = Position(symbol, quantity, price, side, self.leverage, margin)
        trade = {
            "side": f"OPEN_{side}", "symbol": symbol, "price": price,
            "quantity": quantity, "fee": fee, "leverage": self.leverage,
            "margin": margin,
        }
        self.trade_log.append(trade)
        return trade

    def close_position(self, symbol: str, price: float, reason: str | None = None) -> dict:
        if symbol not in self.positions:
            raise ValueError("No open futures position")
        pos = self.positions[symbol]
        gross_pnl = (price - pos.avg_entry_price) * pos.quantity
        if pos.side == "SHORT":
            gross_pnl = -gross_pnl
        fee = pos.quantity * price * self.FUTURES_FEE_RATE
        pnl = gross_pnl - fee
        self.cash += pos.margin + pnl - fee * 0  # fee already included in pnl
        del self.positions[symbol]
        trade = {
            "side": f"CLOSE_{pos.side}", "symbol": symbol, "price": price,
            "quantity": pos.quantity, "fee": fee, "entry_price": pos.avg_entry_price,
            "pnl": pnl, "leverage": pos.leverage, "margin": pos.margin,
        }
        if reason:
            trade["reason"] = reason
        self.trade_log.append(trade)
        return trade

    def unrealized_pnl(self, position: Position, price: float) -> float:
        pnl = (price - position.avg_entry_price) * position.quantity
        return -pnl if position.side == "SHORT" else pnl

    def total_value(self, current_prices: dict[str, float]) -> float:
        value = self.cash
        for symbol, pos in self.positions.items():
            price = current_prices.get(symbol, pos.avg_entry_price)
            value += pos.margin + self.unrealized_pnl(pos, price)
        return value

    def to_state(self) -> dict:
        return {
            "cash": self.cash,
            "positions": {
                symbol: {
                    "quantity": pos.quantity,
                    "avg_entry_price": pos.avg_entry_price,
                    "side": pos.side,
                    "leverage": pos.leverage,
                    "margin": pos.margin,
                }
                for symbol, pos in self.positions.items()
            },
        }

    @classmethod
    def from_state(cls, initial_cash: float, state: dict, leverage: int = 5) -> "FuturesPortfolio":
        portfolio = cls(initial_cash, leverage=leverage)
        portfolio.cash = state["cash"]
        portfolio.positions = {
            symbol: Position(
                symbol, data["quantity"], data["avg_entry_price"],
                data.get("side", "LONG"), data.get("leverage", leverage), data.get("margin", 0.0),
            )
            for symbol, data in state["positions"].items()
        }
        return portfolio
