import threading

from src.storage.db import (
    get_previous_balance_snapshot,
    get_trades_since,
    init_db,
    load_portfolio_state,
    log_trade,
    save_balance_snapshot,
    save_daily_report,
    save_portfolio_state,
)


def make_conn():
    return init_db(":memory:")


def test_save_and_load_portfolio_state_round_trip():
    conn = make_conn()
    save_portfolio_state(
        conn, "trend_follower", 9000.0, {"BTCUSDT": {"quantity": 9.9, "avg_entry_price": 100.0}}
    )
    state = load_portfolio_state(conn, "trend_follower")
    assert state["cash"] == 9000.0
    assert state["positions"]["BTCUSDT"]["quantity"] == 9.9


def test_save_portfolio_state_overwrites_existing():
    conn = make_conn()
    save_portfolio_state(conn, "trend_follower", 9000.0, {})
    save_portfolio_state(conn, "trend_follower", 8000.0, {})
    state = load_portfolio_state(conn, "trend_follower")
    assert state["cash"] == 8000.0


def test_load_portfolio_state_missing_agent_returns_none():
    conn = make_conn()
    assert load_portfolio_state(conn, "unknown_agent") is None


def test_log_trade_and_get_trades_since():
    conn = make_conn()
    log_trade(
        conn, "trend_follower", "BTCUSDT", "BUY", 9.9, 100.0, 1.0, "2026-07-22T01:00:00"
    )
    log_trade(
        conn,
        "trend_follower",
        "BTCUSDT",
        "SELL",
        9.9,
        150.0,
        1.5,
        "2026-07-22T05:00:00",
        entry_price=100.0,
        pnl=493.5,
    )
    trades = get_trades_since(conn, "trend_follower", "2026-07-22T00:00:00")
    assert len(trades) == 2
    assert trades[1]["pnl"] == 493.5


def test_get_trades_since_excludes_earlier_agent_or_date():
    conn = make_conn()
    log_trade(conn, "trend_follower", "BTCUSDT", "BUY", 1.0, 100.0, 0.1, "2026-07-21T01:00:00")
    log_trade(conn, "mean_reversion", "BTCUSDT", "BUY", 1.0, 100.0, 0.1, "2026-07-22T01:00:00")
    trades = get_trades_since(conn, "trend_follower", "2026-07-22T00:00:00")
    assert trades == []


def test_save_daily_report_and_overwrite():
    conn = make_conn()
    save_daily_report(conn, "2026-07-22", "first version")
    save_daily_report(conn, "2026-07-22", "second version")
    row = conn.execute(
        "SELECT report_text FROM daily_reports WHERE report_date = ?", ("2026-07-22",)
    ).fetchone()
    assert row[0] == "second version"


def test_balance_snapshot_and_previous_lookup():
    conn = make_conn()
    save_balance_snapshot(conn, "trend_follower", "2026-07-21", 10_500.0)
    save_balance_snapshot(conn, "trend_follower", "2026-07-22", 10_800.0)
    previous = get_previous_balance_snapshot(conn, "trend_follower", "2026-07-22")
    assert previous == 10_500.0


def test_previous_balance_snapshot_none_when_no_history():
    conn = make_conn()
    assert get_previous_balance_snapshot(conn, "trend_follower", "2026-07-22") is None


def test_connection_allows_writes_from_a_different_thread(tmp_path):
    # Production hands one connection to both the SimulationEngine and the
    # scheduler's daily-report job, and APScheduler runs jobs on worker
    # threads that did not create the connection. sqlite3's default
    # check_same_thread=True would make any cross-thread use raise
    # ProgrammingError. init_db must disable that check so the shared
    # connection works from whatever thread APScheduler picks.
    # A file-backed DB is used (not ":memory:") because in-memory SQLite
    # databases are private to the connection that created them and are not
    # meaningfully shared across threads even with check_same_thread=False -
    # this mirrors what production actually does (a real DB_PATH file).
    conn = init_db(str(tmp_path / "cross_thread.db"))

    errors: list[Exception] = []

    def write_from_other_thread():
        try:
            save_portfolio_state(conn, "trend_follower", 5000.0, {})
        except Exception as exc:  # noqa: BLE001 - we want to capture and assert on it
            errors.append(exc)

    thread = threading.Thread(target=write_from_other_thread)
    thread.start()
    thread.join()

    assert errors == []
    state = load_portfolio_state(conn, "trend_follower")
    assert state["cash"] == 5000.0
