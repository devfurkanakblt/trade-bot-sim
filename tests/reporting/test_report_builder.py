import pytest

from src.portfolio.portfolio import Portfolio
from src.reporting.report_builder import build_daily_report, compute_agent_report


def test_compute_agent_report_basic_fields():
    portfolio = Portfolio(10_000.0)
    portfolio.buy("BTCUSDT", price=100.0, cash_amount=1000.0)
    trades_today = [
        {"side": "SELL", "pnl": 50.0},
        {"side": "SELL", "pnl": -10.0},
    ]

    report = compute_agent_report(
        "trend_follower", portfolio, {"BTCUSDT": 110.0}, trades_today, previous_balance=10_000.0
    )

    assert report["name"] == "trend_follower"
    assert report["open_positions"] == ["BTCUSDT"]
    assert report["trades_today"] == 2
    assert report["win_rate_pct"] == pytest.approx(50.0)
    assert report["total_pnl_abs"] > 0


def test_compute_agent_report_no_sells_gives_zero_win_rate():
    portfolio = Portfolio(10_000.0)
    report = compute_agent_report("mean_reversion", portfolio, {}, [], previous_balance=10_000.0)
    assert report["win_rate_pct"] == 0.0
    assert report["trades_today"] == 0


def test_build_daily_report_ranks_by_total_pnl_pct():
    reports = [
        {
            "name": "agent_low",
            "balance": 9500.0,
            "daily_pnl_abs": -50.0,
            "daily_pnl_pct": -0.5,
            "total_pnl_abs": -500.0,
            "total_pnl_pct": -5.0,
            "open_positions": [],
            "trades_today": 1,
            "win_rate_pct": 0.0,
        },
        {
            "name": "agent_high",
            "balance": 11000.0,
            "daily_pnl_abs": 100.0,
            "daily_pnl_pct": 1.0,
            "total_pnl_abs": 1000.0,
            "total_pnl_pct": 10.0,
            "open_positions": ["BTCUSDT"],
            "trades_today": 2,
            "win_rate_pct": 100.0,
        },
    ]

    text = build_daily_report(reports, "2026-07-22")

    assert text.index("agent_high") < text.index("agent_low")
    assert "2026-07-22" in text
    assert "#1 agent_high" in text
    assert "#2 agent_low" in text
