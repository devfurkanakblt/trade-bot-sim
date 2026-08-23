import datetime
import sqlite3

from src.storage.backup import backup_database
from src.storage.db import init_db, save_portfolio_state


def test_backup_database_copies_a_consistent_database(tmp_path):
    source = tmp_path / "trade_bot_sim.db"
    conn = init_db(str(source))
    save_portfolio_state(conn, "grid_trader", 9_500.0, {})
    conn.close()

    backup = backup_database(source, tmp_path / "backups")

    backup_conn = sqlite3.connect(backup)
    row = backup_conn.execute(
        "SELECT cash FROM portfolios WHERE agent_name = ?", ("grid_trader",)
    ).fetchone()
    backup_conn.close()
    assert row == (9_500.0,)


def test_backup_database_retains_only_requested_number(tmp_path):
    source = tmp_path / "trade_bot_sim.db"
    init_db(str(source)).close()
    backup_dir = tmp_path / "backups"

    for day in range(1, 4):
        backup_database(
            source,
            backup_dir,
            keep=2,
            now=datetime.datetime(2026, 8, day, tzinfo=datetime.UTC),
        )

    assert len(list(backup_dir.glob("trade_bot_sim-*.db"))) == 2
