import datetime
import logging

from src.portfolio.portfolio import Portfolio
from src.storage.db import log_trade, save_portfolio_state
from src.strategies.base import Action

logger = logging.getLogger(__name__)

POSITION_SIZE_PCT = 0.25
STOP_LOSS_PCT = 0.05


class Agent:
    def __init__(self, name: str, strategy, portfolio: Portfolio):
        self.name = name
        self.strategy = strategy
        self.portfolio = portfolio


class SimulationEngine:
    def __init__(self, agents: list[Agent], market_data_client, storage_conn):
        self.agents = agents
        self.market_data = market_data_client
        self.storage = storage_conn

    def run_tick(self, watchlist: list[str]) -> None:
        candles_by_symbol = {symbol: self.market_data.get_klines(symbol) for symbol in watchlist}
        prices_by_symbol = {symbol: candles_by_symbol[symbol][-1]["close"] for symbol in watchlist}

        for agent in self.agents:
            try:
                self._run_agent_tick(agent, watchlist, candles_by_symbol, prices_by_symbol)
            except Exception:
                logger.exception("Agent %s failed this tick", agent.name)

    def _run_agent_tick(self, agent, watchlist, candles_by_symbol, prices_by_symbol) -> None:
        try:
            self._apply_stop_losses(agent, prices_by_symbol)
            for symbol in watchlist:
                signal = agent.strategy.generate_signal(symbol, candles_by_symbol[symbol])
                price = prices_by_symbol[symbol]
                if signal.action == Action.BUY:
                    self._execute_buy(agent, symbol, price, prices_by_symbol)
                elif signal.action == Action.SELL:
                    self._execute_sell(agent, symbol, price)
        finally:
            state = agent.portfolio.to_state()
            save_portfolio_state(self.storage, agent.name, state["cash"], state["positions"])

    def _apply_stop_losses(self, agent: Agent, prices_by_symbol: dict[str, float]) -> None:
        for symbol, position in list(agent.portfolio.positions.items()):
            current_price = prices_by_symbol.get(symbol)
            if current_price is None:
                continue
            loss_pct = (position.avg_entry_price - current_price) / position.avg_entry_price
            if loss_pct >= STOP_LOSS_PCT:
                self._execute_sell(agent, symbol, current_price)

    def _execute_buy(self, agent: Agent, symbol: str, price: float, prices_by_symbol: dict[str, float]) -> None:
        portfolio_value = agent.portfolio.total_value(prices_by_symbol)
        max_position_value = portfolio_value * POSITION_SIZE_PCT

        existing_value = 0.0
        if symbol in agent.portfolio.positions:
            existing_value = agent.portfolio.positions[symbol].quantity * price

        available_to_buy = max(0.0, max_position_value - existing_value)
        cash_to_spend = min(available_to_buy, agent.portfolio.cash)
        if cash_to_spend <= 0:
            return

        agent.portfolio.buy(symbol, price, cash_to_spend)
        self._log_trade(agent, symbol)

    def _execute_sell(self, agent: Agent, symbol: str, price: float) -> None:
        if symbol not in agent.portfolio.positions:
            return
        quantity = agent.portfolio.positions[symbol].quantity
        agent.portfolio.sell(symbol, price, quantity)
        self._log_trade(agent, symbol)

    def _log_trade(self, agent: Agent, symbol: str) -> None:
        trade = agent.portfolio.trade_log[-1]
        log_trade(
            self.storage,
            agent.name,
            symbol,
            trade["side"],
            trade["quantity"],
            trade["price"],
            trade["fee"],
            datetime.datetime.now(datetime.UTC).isoformat(),
            entry_price=trade.get("entry_price"),
            pnl=trade.get("pnl"),
        )
