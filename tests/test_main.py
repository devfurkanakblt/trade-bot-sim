import datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from src.config import Config
from src.storage.db import init_db, save_portfolio_state

import main


def make_config(tmp_path):
    config = Config()
    config.DB_PATH = str(tmp_path / "test.db")
    return config


def test_build_agents_creates_five_agents_with_fresh_state(tmp_path):
    config = make_config(tmp_path)
    conn = init_db(config.DB_PATH)

    agents = main.build_agents(conn, config)

    assert len(agents) == 5
    names = {agent.name for agent in agents}
    assert names == {
        "trend_follower",
        "mean_reversion",
        "momentum_breakout",
        "grid_trader",
        "ml_predictor",
    }
    for agent in agents:
        assert agent.portfolio.cash == config.INITIAL_BALANCE


def test_build_agents_restores_existing_state_from_storage(tmp_path):
    config = make_config(tmp_path)
    conn = init_db(config.DB_PATH)
    save_portfolio_state(conn, "trend_follower", 8000.0, {"BTCUSDT": {"quantity": 1.0, "avg_entry_price": 100.0}})

    agents = main.build_agents(conn, config)

    trend_agent = next(a for a in agents if a.name == "trend_follower")
    assert trend_agent.portfolio.cash == 8000.0
    assert "BTCUSDT" in trend_agent.portfolio.positions


def test_daily_report_sends_notification_with_report_text(tmp_path):
    config = make_config(tmp_path)
    conn = init_db(config.DB_PATH)
    agents = main.build_agents(conn, config)

    fake_market_data = MagicMock()
    fake_market_data.get_current_price.return_value = 100.0
    fake_notifier = MagicMock()

    daily_report = main.make_daily_report(conn, fake_market_data, agents, fake_notifier, config)
    daily_report()

    fake_notifier.send_report.assert_called_once()
    args, _ = fake_notifier.send_report.call_args
    title, body = args
    assert "Daily Report" in title
    assert "trend_follower" in body


def test_daily_report_dates_using_istanbul_timezone_not_local_clock(tmp_path):
    # The scheduler fires on Europe/Istanbul time, and trades are timestamped
    # in UTC, but the report's date label must come from Europe/Istanbul (not
    # whatever timezone the host's system clock happens to be set to) so the
    # label agrees with the scheduler's own notion of "today". Compute the
    # expected date the same way production does and confirm that is what
    # gets persisted as the report_date, rather than the host's local date.
    config = make_config(tmp_path)
    conn = init_db(config.DB_PATH)
    agents = main.build_agents(conn, config)

    fake_market_data = MagicMock()
    fake_market_data.get_current_price.return_value = 100.0
    fake_notifier = MagicMock()

    daily_report = main.make_daily_report(conn, fake_market_data, agents, fake_notifier, config)
    daily_report()

    expected_date = datetime.datetime.now(ZoneInfo("Europe/Istanbul")).date().isoformat()
    row = conn.execute("SELECT report_date FROM daily_reports").fetchone()
    assert row[0] == expected_date


def test_hourly_tick_calls_engine_run_tick():
    fake_engine = MagicMock()
    config = Config()

    hourly_tick = main.make_hourly_tick(fake_engine, config)
    hourly_tick()

    fake_engine.run_tick.assert_called_once_with(config.WATCHLIST)
