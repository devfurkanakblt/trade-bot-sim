import datetime
import logging

from src.config import Config
from src.data.binance_client import MarketDataClient
from src.engine.simulation_engine import Agent, SimulationEngine
from src.notifier.pushbullet_notifier import PushbulletNotifier
from src.portfolio.portfolio import Portfolio
from src.reporting.report_builder import build_daily_report, compute_agent_report
from src.scheduler.jobs import build_scheduler
from src.storage.db import (
    get_previous_balance_snapshot,
    get_trades_since,
    init_db,
    load_portfolio_state,
    save_balance_snapshot,
    save_daily_report,
)
from src.strategies.grid_trader import GridTraderStrategy
from src.strategies.mean_reversion import MeanReversionStrategy
from src.strategies.ml_predictor import MLPredictorStrategy
from src.strategies.momentum_breakout import MomentumBreakoutStrategy
from src.strategies.trend_follower import TrendFollowerStrategy

STRATEGY_CLASSES = {
    "trend_follower": TrendFollowerStrategy,
    "mean_reversion": MeanReversionStrategy,
    "momentum_breakout": MomentumBreakoutStrategy,
    "grid_trader": GridTraderStrategy,
    "ml_predictor": MLPredictorStrategy,
}


def build_agents(conn, config: Config) -> list[Agent]:
    agents = []
    for name, strategy_cls in STRATEGY_CLASSES.items():
        state = load_portfolio_state(conn, name)
        if state is not None:
            portfolio = Portfolio.from_state(config.INITIAL_BALANCE, state)
        else:
            portfolio = Portfolio(config.INITIAL_BALANCE)
        agents.append(Agent(name, strategy_cls(), portfolio))
    return agents


def make_hourly_tick(engine: SimulationEngine, config: Config):
    def hourly_tick() -> None:
        engine.run_tick(config.WATCHLIST)

    return hourly_tick


def make_daily_report(conn, market_data, agents: list[Agent], notifier, config: Config):
    def daily_report() -> None:
        today = datetime.date.today().isoformat()
        current_prices = {symbol: market_data.get_current_price(symbol) for symbol in config.WATCHLIST}

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


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    config = Config()
    conn = init_db(config.DB_PATH)
    market_data = MarketDataClient()
    notifier = PushbulletNotifier(config.PUSHBULLET_TOKEN)

    agents = build_agents(conn, config)
    engine = SimulationEngine(agents, market_data, conn)

    hourly_tick = make_hourly_tick(engine, config)
    daily_report = make_daily_report(conn, market_data, agents, notifier, config)

    scheduler = build_scheduler(hourly_tick, daily_report)
    scheduler.start()


if __name__ == "__main__":
    main()
