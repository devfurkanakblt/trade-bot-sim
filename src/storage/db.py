import json
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS portfolios (
    agent_name TEXT PRIMARY KEY,
    cash REAL NOT NULL,
    positions_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    fee REAL NOT NULL,
    entry_price REAL,
    pnl REAL,
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_reports (
    report_date TEXT PRIMARY KEY,
    report_text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS balance_snapshots (
    agent_name TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    balance REAL NOT NULL,
    PRIMARY KEY (agent_name, snapshot_date)
);
"""


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def save_portfolio_state(conn: sqlite3.Connection, agent_name: str, cash: float, positions: dict) -> None:
    conn.execute(
        "INSERT INTO portfolios (agent_name, cash, positions_json) VALUES (?, ?, ?) "
        "ON CONFLICT(agent_name) DO UPDATE SET cash=excluded.cash, positions_json=excluded.positions_json",
        (agent_name, cash, json.dumps(positions)),
    )
    conn.commit()


def load_portfolio_state(conn: sqlite3.Connection, agent_name: str) -> dict | None:
    row = conn.execute(
        "SELECT cash, positions_json FROM portfolios WHERE agent_name = ?", (agent_name,)
    ).fetchone()
    if row is None:
        return None
    cash, positions_json = row
    return {"cash": cash, "positions": json.loads(positions_json)}


def log_trade(
    conn: sqlite3.Connection,
    agent_name: str,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    fee: float,
    timestamp: str,
    entry_price: float | None = None,
    pnl: float | None = None,
) -> None:
    conn.execute(
        "INSERT INTO trades (agent_name, symbol, side, quantity, price, fee, entry_price, pnl, timestamp) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (agent_name, symbol, side, quantity, price, fee, entry_price, pnl, timestamp),
    )
    conn.commit()


def get_trades_since(conn: sqlite3.Connection, agent_name: str, since_timestamp: str) -> list[dict]:
    rows = conn.execute(
        "SELECT symbol, side, quantity, price, fee, entry_price, pnl, timestamp FROM trades "
        "WHERE agent_name = ? AND timestamp >= ? ORDER BY timestamp",
        (agent_name, since_timestamp),
    ).fetchall()
    return [
        {
            "symbol": r[0],
            "side": r[1],
            "quantity": r[2],
            "price": r[3],
            "fee": r[4],
            "entry_price": r[5],
            "pnl": r[6],
            "timestamp": r[7],
        }
        for r in rows
    ]


def save_daily_report(conn: sqlite3.Connection, report_date: str, report_text: str) -> None:
    conn.execute(
        "INSERT INTO daily_reports (report_date, report_text) VALUES (?, ?) "
        "ON CONFLICT(report_date) DO UPDATE SET report_text=excluded.report_text",
        (report_date, report_text),
    )
    conn.commit()


def save_balance_snapshot(conn: sqlite3.Connection, agent_name: str, snapshot_date: str, balance: float) -> None:
    conn.execute(
        "INSERT INTO balance_snapshots (agent_name, snapshot_date, balance) VALUES (?, ?, ?) "
        "ON CONFLICT(agent_name, snapshot_date) DO UPDATE SET balance=excluded.balance",
        (agent_name, snapshot_date, balance),
    )
    conn.commit()


def get_previous_balance_snapshot(conn: sqlite3.Connection, agent_name: str, before_date: str) -> float | None:
    row = conn.execute(
        "SELECT balance FROM balance_snapshots WHERE agent_name = ? AND snapshot_date < ? "
        "ORDER BY snapshot_date DESC LIMIT 1",
        (agent_name, before_date),
    ).fetchone()
    return row[0] if row is not None else None
