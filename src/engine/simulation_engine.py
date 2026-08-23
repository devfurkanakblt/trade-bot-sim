import datetime
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.portfolio.portfolio import Portfolio
from src.storage.db import log_trade, save_portfolio_state
from src.strategies.base import Action

logger = logging.getLogger(__name__)

POSITION_SIZE_PCT = 0.25
STOP_LOSS_PCT = 0.05
FUTURES_STOP_LOSS_PCT = 0.02
LIQUIDATION_LOSS_OF_MARGIN_PCT = 0.90
MARKET_FETCH_WORKERS = 10


class Agent:
    def __init__(
        self,
        name: str,
        strategy,
        portfolio: Portfolio,
        position_size_pct: float = POSITION_SIZE_PCT,
    ):
        self.name = name
        self.strategy = strategy
        self.portfolio = portfolio
        self.position_size_pct = position_size_pct


class SimulationEngine:
    def __init__(self, agents: list[Agent], market_data_client, storage_conn, live_state=None):
        self.agents = agents
        self.market_data = market_data_client
        self.storage = storage_conn
        self.live_state = live_state
        self._last_processed_open_time: dict[str, int] = {}

    def run_tick(
        self,
        watchlist: list[str],
        interval: str = "1h",
        risk_symbols: list[str] | None = None,
    ) -> None:
        candles_by_symbol = self._fetch_candles(watchlist, interval)
        if not candles_by_symbol:
            logger.warning("No candle data was available; tick skipped")
            return
        candles_by_symbol = self._only_new_candles(candles_by_symbol)
        if not candles_by_symbol:
            logger.info("No newly closed candles were available; tick skipped")
            return
        available_watchlist = [symbol for symbol in watchlist if symbol in candles_by_symbol]
        prices_by_symbol = {symbol: candles_by_symbol[symbol][-1]["close"] for symbol in available_watchlist}
        risk_only_symbols = [
            symbol for symbol in (risk_symbols or []) if symbol not in prices_by_symbol
        ]
        prices_by_symbol.update(self._fetch_current_prices(risk_only_symbols))

        if self.live_state is not None:
            self.live_state.update_candles(candles_by_symbol)

        for agent in self.agents:
            try:
                self._run_agent_tick(agent, available_watchlist, candles_by_symbol, prices_by_symbol)
            except Exception:
                logger.exception("Agent %s failed this tick", agent.name)

    def _only_new_candles(self, candles_by_symbol: dict[str, list[dict]]) -> dict[str, list[dict]]:
        """Return symbols whose most recent closed candle was not processed yet."""
        fresh: dict[str, list[dict]] = {}
        for symbol, candles in candles_by_symbol.items():
            if not candles:
                continue
            open_time = candles[-1].get("open_time")
            # Test doubles and third-party clients may omit open_time. They
            # remain supported, but Binance candles always carry this cursor.
            if open_time is None:
                fresh[symbol] = candles
                continue
            if open_time <= self._last_processed_open_time.get(symbol, -1):
                continue
            self._last_processed_open_time[symbol] = open_time
            fresh[symbol] = candles
        return fresh

    def _fetch_candles(self, watchlist: list[str], interval: str) -> dict[str, list[dict]]:
        """Fetch the larger dynamic market universe without serial API latency."""
        candles_by_symbol: dict[str, list[dict]] = {}
        if not watchlist:
            return candles_by_symbol
        with ThreadPoolExecutor(max_workers=min(MARKET_FETCH_WORKERS, len(watchlist))) as executor:
            requests = {
                executor.submit(self.market_data.get_klines, symbol, interval=interval): symbol
                for symbol in watchlist
            }
            for request in as_completed(requests):
                symbol = requests[request]
                try:
                    candles = request.result()
                    if candles:
                        candles_by_symbol[symbol] = candles
                    else:
                        logger.warning("No candles returned for %s", symbol)
                except Exception:
                    logger.exception("Could not fetch candles for %s", symbol)
        return candles_by_symbol

    def _fetch_current_prices(self, symbols: list[str]) -> dict[str, float]:
        """Fetch lightweight prices for open positions outside the strategy universe."""
        prices: dict[str, float] = {}
        if not symbols:
            return prices
        with ThreadPoolExecutor(max_workers=min(MARKET_FETCH_WORKERS, len(symbols))) as executor:
            requests = {
                executor.submit(self.market_data.get_current_price, symbol): symbol
                for symbol in symbols
            }
            for request in as_completed(requests):
                symbol = requests[request]
                try:
                    prices[symbol] = request.result()
                except Exception:
                    logger.exception("Could not fetch risk price for %s", symbol)
        return prices

    def _run_agent_tick(self, agent, watchlist, candles_by_symbol, prices_by_symbol) -> None:
        decision = "HOLD"
        decision_symbol = None
        try:
            risk_closed_symbols = self._apply_stop_losses(agent, prices_by_symbol)
            for symbol in watchlist:
                # A stop or liquidation is a risk-control exit, not an
                # opportunity to reopen on the very same stale candle.
                if symbol in risk_closed_symbols:
                    continue
                signal = agent.strategy.generate_signal(symbol, candles_by_symbol[symbol])
                price = prices_by_symbol[symbol]
                if signal.action == Action.BUY:
                    if self._execute_signal(agent, symbol, price, prices_by_symbol, "BUY"):
                        decision, decision_symbol = self._decision_label(agent, "BUY"), symbol
                elif signal.action == Action.SELL:
                    if self._execute_signal(agent, symbol, price, prices_by_symbol, "SELL"):
                        decision, decision_symbol = self._decision_label(agent, "SELL"), symbol
        finally:
            state = agent.portfolio.to_state()
            save_portfolio_state(self.storage, agent.name, state["cash"], state["positions"])
            self._update_live_state(agent, decision, decision_symbol, prices_by_symbol)

    def _apply_stop_losses(self, agent: Agent, prices_by_symbol: dict[str, float]) -> set[str]:
        closed_symbols: set[str] = set()
        for symbol, position in list(agent.portfolio.positions.items()):
            current_price = prices_by_symbol.get(symbol)
            if current_price is None:
                continue
            if agent.portfolio.is_leveraged:
                price_move = (current_price - position.avg_entry_price) / position.avg_entry_price
                loss_pct = -price_move if position.side == "LONG" else price_move
                margin_loss = (
                    -agent.portfolio.unrealized_pnl(position, current_price) / position.margin
                    if position.margin > 0
                    else 0.0
                )
                if margin_loss >= LIQUIDATION_LOSS_OF_MARGIN_PCT:
                    if self._execute_futures_close(agent, symbol, current_price, "LIQUIDATION"):
                        closed_symbols.add(symbol)
                elif loss_pct >= FUTURES_STOP_LOSS_PCT:
                    if self._execute_futures_close(agent, symbol, current_price, "STOP_LOSS"):
                        closed_symbols.add(symbol)
            else:
                loss_pct = (position.avg_entry_price - current_price) / position.avg_entry_price
                if loss_pct >= STOP_LOSS_PCT:
                    if self._execute_sell(agent, symbol, current_price):
                        closed_symbols.add(symbol)
        return closed_symbols

    def _execute_signal(
        self, agent: Agent, symbol: str, price: float, prices_by_symbol: dict[str, float], action: str
    ) -> bool:
        if agent.portfolio.is_leveraged:
            return self._execute_futures_signal(agent, symbol, price, prices_by_symbol, action)
        if action == "BUY":
            return self._execute_buy(agent, symbol, price, prices_by_symbol)
        return self._execute_sell(agent, symbol, price)

    def _decision_label(self, agent: Agent, action: str) -> str:
        if not agent.portfolio.is_leveraged:
            return action
        return "LONG" if action == "BUY" else "SHORT"

    def _execute_buy(self, agent: Agent, symbol: str, price: float, prices_by_symbol: dict[str, float]) -> bool:
        portfolio_value = agent.portfolio.total_value(prices_by_symbol)
        max_position_value = portfolio_value * agent.position_size_pct

        existing_value = 0.0
        if symbol in agent.portfolio.positions:
            existing_value = agent.portfolio.positions[symbol].quantity * price

        available_to_buy = max(0.0, max_position_value - existing_value)
        cash_to_spend = min(available_to_buy, agent.portfolio.cash)
        if cash_to_spend <= 0:
            return False

        agent.portfolio.buy(symbol, price, cash_to_spend)
        self._log_trade(agent, symbol)
        return True

    def _execute_futures_signal(
        self, agent: Agent, symbol: str, price: float, prices_by_symbol: dict[str, float], action: str
    ) -> bool:
        desired_side = "LONG" if action == "BUY" else "SHORT"
        current = agent.portfolio.positions.get(symbol)
        if current is not None:
            if current.side == desired_side:
                return False
            self._execute_futures_close(agent, symbol, price, "SIGNAL_FLIP")

        portfolio_value = agent.portfolio.total_value(prices_by_symbol)
        margin = min(
            portfolio_value * agent.position_size_pct,
            agent.portfolio.cash / (1 + agent.portfolio.leverage * agent.portfolio.FUTURES_FEE_RATE),
        )
        if margin <= 0:
            return False
        agent.portfolio.open_position(symbol, price, margin, desired_side)
        self._log_trade(agent, symbol)
        return True

    def _execute_futures_close(self, agent: Agent, symbol: str, price: float, reason: str) -> bool:
        if symbol not in agent.portfolio.positions:
            return False
        agent.portfolio.close_position(symbol, price, reason=reason)
        self._log_trade(agent, symbol)
        return True

    def _execute_sell(self, agent: Agent, symbol: str, price: float) -> bool:
        if symbol not in agent.portfolio.positions:
            return False
        quantity = agent.portfolio.positions[symbol].quantity
        agent.portfolio.sell(symbol, price, quantity)
        self._log_trade(agent, symbol)
        return True

    def _update_live_state(self, agent, decision, decision_symbol, prices_by_symbol) -> None:
        if self.live_state is None:
            return
        pnl_abs, pnl_pct = agent.portfolio.total_pnl(prices_by_symbol)
        total_value = agent.portfolio.total_value(prices_by_symbol)
        positions = {
            symbol: {
                "quantity": pos.quantity,
                "avg_entry_price": pos.avg_entry_price,
                "side": pos.side,
                "leverage": pos.leverage,
            }
            for symbol, pos in agent.portfolio.positions.items()
        }
        self.live_state.update_agent(
            name=agent.name,
            decision=decision,
            symbol=decision_symbol,
            pnl_abs=pnl_abs,
            pnl_pct=pnl_pct,
            cash=agent.portfolio.cash,
            total_value=total_value,
            positions=positions,
            mode="FUTURES" if agent.portfolio.is_leveraged else "SPOT",
            leverage=getattr(agent.portfolio, "leverage", 1),
        )

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
