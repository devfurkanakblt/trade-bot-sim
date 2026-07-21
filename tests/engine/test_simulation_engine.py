from src.engine.simulation_engine import Agent, SimulationEngine
from src.portfolio.portfolio import Portfolio
from src.storage.db import get_trades_since, init_db, load_portfolio_state
from src.strategies.base import Action, BaseStrategy, Signal


class FixedSignalStrategy(BaseStrategy):
    name = "fixed"

    def __init__(self, action: Action):
        self.action = action

    def generate_signal(self, symbol, candles):
        return Signal(self.action, symbol)


class ExplodingStrategy(BaseStrategy):
    name = "exploding"

    def generate_signal(self, symbol, candles):
        raise RuntimeError("strategy bug")


class BuyThenExplodeStrategy(BaseStrategy):
    """Succeeds with a BUY signal for the first symbol it sees, then raises for any subsequent symbol."""

    name = "buy_then_explode"

    def __init__(self):
        self.calls = 0

    def generate_signal(self, symbol, candles):
        self.calls += 1
        if self.calls == 1:
            return Signal(Action.BUY, symbol)
        raise RuntimeError("strategy bug on second symbol")


class FakeMarketDataClient:
    def __init__(self, price: float = 100.0):
        self.price = price

    def get_klines(self, symbol, interval="1h", limit=100):
        return [{"close": self.price, "open": self.price, "high": self.price, "low": self.price, "volume": 1.0, "open_time": 0}]


def make_conn():
    return init_db(":memory:")


def test_buy_signal_executes_buy_and_saves_state():
    conn = make_conn()
    agent = Agent("agent_a", FixedSignalStrategy(Action.BUY), Portfolio(10_000.0))
    engine = SimulationEngine([agent], FakeMarketDataClient(price=100.0), conn)

    engine.run_tick(["BTCUSDT"])

    assert "BTCUSDT" in agent.portfolio.positions
    saved_state = load_portfolio_state(conn, "agent_a")
    assert saved_state is not None
    assert saved_state["cash"] < 10_000.0


def test_position_size_capped_at_pct_of_portfolio():
    conn = make_conn()
    agent = Agent("agent_a", FixedSignalStrategy(Action.BUY), Portfolio(10_000.0))
    engine = SimulationEngine([agent], FakeMarketDataClient(price=100.0), conn)

    engine.run_tick(["BTCUSDT"])

    position_value = agent.portfolio.positions["BTCUSDT"].quantity * 100.0
    assert position_value <= 10_000.0 * 0.25 + 1e-6


def test_sell_signal_executes_sell():
    conn = make_conn()
    portfolio = Portfolio(10_000.0)
    portfolio.buy("BTCUSDT", price=100.0, cash_amount=1000.0)
    agent = Agent("agent_a", FixedSignalStrategy(Action.SELL), portfolio)
    engine = SimulationEngine([agent], FakeMarketDataClient(price=100.0), conn)

    engine.run_tick(["BTCUSDT"])

    assert "BTCUSDT" not in agent.portfolio.positions


def test_stop_loss_triggers_sell_before_new_signals():
    conn = make_conn()
    portfolio = Portfolio(10_000.0)
    portfolio.buy("BTCUSDT", price=100.0, cash_amount=1000.0)
    agent = Agent("agent_a", FixedSignalStrategy(Action.HOLD), portfolio)
    # price has dropped 6%, past the 5% stop-loss threshold
    engine = SimulationEngine([agent], FakeMarketDataClient(price=94.0), conn)

    engine.run_tick(["BTCUSDT"])

    assert "BTCUSDT" not in agent.portfolio.positions


def test_agent_exception_does_not_stop_other_agents():
    conn = make_conn()
    broken_agent = Agent("broken", ExplodingStrategy(), Portfolio(10_000.0))
    healthy_agent = Agent("healthy", FixedSignalStrategy(Action.BUY), Portfolio(10_000.0))
    engine = SimulationEngine([broken_agent, healthy_agent], FakeMarketDataClient(price=100.0), conn)

    engine.run_tick(["BTCUSDT"])

    assert "BTCUSDT" in healthy_agent.portfolio.positions


def test_trade_is_logged_to_storage():
    conn = make_conn()
    agent = Agent("agent_a", FixedSignalStrategy(Action.BUY), Portfolio(10_000.0))
    engine = SimulationEngine([agent], FakeMarketDataClient(price=100.0), conn)

    engine.run_tick(["BTCUSDT"])

    trades = get_trades_since(conn, "agent_a", "1970-01-01T00:00:00")
    assert len(trades) == 1
    assert trades[0]["side"] == "BUY"


def test_partial_tick_progress_is_persisted_when_strategy_raises_midway():
    conn = make_conn()
    agent = Agent("agent_a", BuyThenExplodeStrategy(), Portfolio(10_000.0))
    engine = SimulationEngine([agent], FakeMarketDataClient(price=100.0), conn)

    # run_tick must not raise: the outer try/except in run_tick still catches
    # and logs the exception exactly as before.
    engine.run_tick(["BTCUSDT", "ETHUSDT"])

    # The first symbol's buy executed in-memory...
    assert "BTCUSDT" in agent.portfolio.positions
    assert agent.portfolio.cash < 10_000.0

    # ...and that partial progress must be persisted to storage even though the
    # tick raised partway through the watchlist loop on the second symbol.
    saved_state = load_portfolio_state(conn, "agent_a")
    assert saved_state is not None
    assert saved_state["cash"] == agent.portfolio.cash
    assert "BTCUSDT" in saved_state["positions"]
