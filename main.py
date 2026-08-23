import datetime
import logging
import threading
import time
from zoneinfo import ZoneInfo

from src.config import Config
from src.data.binance_client import MarketDataClient, MarketDataError
from src.engine.simulation_engine import Agent, SimulationEngine
from src.notifier.pushbullet_notifier import PushbulletNotifier
from src.portfolio.portfolio import FuturesPortfolio, Portfolio
from src.reporting.report_builder import build_daily_report, compute_agent_report
from src.scheduler.jobs import build_scheduler
from src.storage.db import (
    get_previous_balance_snapshot,
    get_trades_since,
    init_db,
    load_portfolio_state,
    save_balance_snapshot,
    save_daily_report,
    save_equity_snapshot,
)
from src.strategies.grid_trader import GridTraderStrategy
from src.strategies.mean_reversion import MeanReversionStrategy
from src.strategies.ml_predictor import MLPredictorStrategy
from src.strategies.momentum_breakout import MomentumBreakoutStrategy
from src.strategies.leveraged_breakout import LeveragedBreakoutStrategy
from src.strategies.scalper import LeveragedScalperStrategy, ScalperStrategy
from src.strategies.trend_follower import TrendFollowerStrategy
from src.web.dashboard import run_dashboard
from src.web.live_state import LiveState

STRATEGY_CLASSES = {
    "trend_follower": TrendFollowerStrategy,
    "mean_reversion": MeanReversionStrategy,
    "momentum_breakout": MomentumBreakoutStrategy,
    "grid_trader": GridTraderStrategy,
    "ml_predictor": MLPredictorStrategy,
    "scalper": ScalperStrategy,
    "leveraged_scalper": LeveragedScalperStrategy,
    "leveraged_breakout": LeveragedBreakoutStrategy,
}

LEVERAGED_AGENT_LEVERAGE = {
    "leveraged_scalper": 5,
    "leveraged_breakout": 3,
}


class MarketUniverse:
    """Caches Binance's volume-ranked market universe between refreshes."""

    def __init__(self, market_data: MarketDataClient, config: Config):
        self.market_data = market_data
        self.config = config
        self._symbols: list[str] = list(config.WATCHLIST)
        self._refreshed_at = 0.0

    def get_symbols(self) -> list[str]:
        now = time.monotonic()
        if now - self._refreshed_at < self.config.MARKET_UNIVERSE_REFRESH_SECONDS:
            return list(self._symbols)
        try:
            symbols = self.market_data.get_popular_usdt_pairs(self.config.MARKET_UNIVERSE_SIZE)
            if not symbols:
                raise MarketDataError("Popular-market response was empty")
            self._symbols = symbols
            self._refreshed_at = now
            logging.info("Piyasa evreni yenilendi: %d USDT paritesi", len(symbols))
        except MarketDataError as exc:
            # Do not turn a temporary universe endpoint outage into a stopped
            # simulator; continue with the last known liquid universe.
            logging.warning("Piyasa evreni yenilenemedi, mevcut liste kullanılıyor: %s", exc)
            self._refreshed_at = now
        return list(self._symbols)


def include_open_position_symbols(symbols: list[str], agents: list[Agent]) -> list[str]:
    """Keep risk controls active when a previously popular market drops in rank."""
    open_symbols = [symbol for agent in agents for symbol in agent.portfolio.positions]
    return list(dict.fromkeys([*symbols, *open_symbols]))


def build_agents(conn, config: Config) -> list[Agent]:
    agents = []
    for name, strategy_cls in STRATEGY_CLASSES.items():
        state = load_portfolio_state(conn, name)
        leverage = LEVERAGED_AGENT_LEVERAGE.get(name)
        if leverage is not None and state is not None:
            portfolio = FuturesPortfolio.from_state(config.INITIAL_BALANCE, state, leverage=leverage)
        elif leverage is not None:
            portfolio = FuturesPortfolio(config.INITIAL_BALANCE, leverage=leverage)
        elif state is not None:
            portfolio = Portfolio.from_state(config.INITIAL_BALANCE, state)
        else:
            portfolio = Portfolio(config.INITIAL_BALANCE)
        # Futures agents put up a smaller isolated margin per pair, while the
        # position's notional is expanded only by its explicit leverage.
        position_size_pct = 0.08 if leverage is not None else 0.25
        agents.append(Agent(name, strategy_cls(), portfolio, position_size_pct=position_size_pct))
    return agents


def make_minute_tick(engine: SimulationEngine, config: Config, market_universe: MarketUniverse | None = None):
    def minute_tick() -> None:
        watchlist = market_universe.get_symbols() if market_universe else config.WATCHLIST
        watchlist = include_open_position_symbols(watchlist, engine.agents)
        engine.run_tick(watchlist, interval=config.KLINE_INTERVAL)

    return minute_tick


def make_daily_report(conn, market_data, agents: list[Agent], notifier, config: Config, market_universe: MarketUniverse | None = None):
    def daily_report() -> None:
        # Use Europe/Istanbul (the scheduler's own timezone) rather than the
        # local system clock: on a UTC-clocked host, datetime.date.today() at
        # 00:00 Istanbul time can still report the previous UTC day, mis-dating
        # the report.
        today = datetime.datetime.now(ZoneInfo("Europe/Istanbul")).date().isoformat()
        watchlist = market_universe.get_symbols() if market_universe else config.WATCHLIST
        watchlist = include_open_position_symbols(watchlist, agents)
        current_prices = {symbol: market_data.get_current_price(symbol) for symbol in watchlist}

        agent_reports = []
        for agent in agents:
            previous_balance = get_previous_balance_snapshot(conn, agent.name, today)
            if previous_balance is None:
                previous_balance = config.INITIAL_BALANCE
            trades_today = get_trades_since(conn, agent.name, f"{today}T00:00:00")
            report = compute_agent_report(agent.name, agent.portfolio, current_prices, trades_today, previous_balance)
            agent_reports.append(report)
            save_balance_snapshot(conn, agent.name, today, report["balance"])

        report_text = build_daily_report(agent_reports, today)
        save_daily_report(conn, today, report_text)
        notifier.send_report("Trade Bot Sim - Daily Report", report_text)

    return daily_report


def make_hourly_snapshot(conn, market_data, agents: list[Agent]):
    def hourly_snapshot() -> None:
        snapshot_timestamp = (
            datetime.datetime.now(datetime.UTC)
            .replace(minute=0, second=0, microsecond=0)
            .isoformat()
        )
        open_symbols = list(
            dict.fromkeys(symbol for agent in agents for symbol in agent.portfolio.positions)
        )
        current_prices: dict[str, float] = {}
        for symbol in open_symbols:
            try:
                current_prices[symbol] = market_data.get_current_price(symbol)
            except MarketDataError as exc:
                # Portfolio.total_value falls back to the entry price for a
                # missing symbol, so one temporary API failure does not erase
                # the rest of the hourly equity curve.
                logging.warning("Saatlik snapshot fiyatı alınamadı (%s): %s", symbol, exc)

        for agent in agents:
            save_equity_snapshot(
                conn,
                agent.name,
                snapshot_timestamp,
                agent.portfolio.total_value(current_prices),
                agent.portfolio.cash,
                len(agent.portfolio.positions),
            )

    return hourly_snapshot


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    config = Config()
    conn = init_db(config.DB_PATH)
    market_data = MarketDataClient()
    notifier = PushbulletNotifier(config.PUSHBULLET_TOKEN)

    live_state = LiveState()
    agents = build_agents(conn, config)
    engine = SimulationEngine(agents, market_data, conn, live_state=live_state)
    market_universe = MarketUniverse(market_data, config)

    minute_tick = make_minute_tick(engine, config, market_universe)
    hourly_snapshot = make_hourly_snapshot(conn, market_data, agents)
    daily_report = make_daily_report(conn, market_data, agents, notifier, config, market_universe)

    web_thread = threading.Thread(
        target=run_dashboard, args=(live_state, config.WEB_PORT, conn), daemon=True
    )
    web_thread.start()
    logging.info("Canlı panel: http://127.0.0.1:%d", config.WEB_PORT)

    scheduler = build_scheduler(minute_tick, hourly_snapshot, daily_report)
    scheduler.start()


if __name__ == "__main__":
    main()
