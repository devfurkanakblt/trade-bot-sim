# Crypto Paper-Trading Simulation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 24/7 crypto paper-trading simulation with 5 independent strategy agents, each trading a shared virtual $10,000 balance against live Binance market data, culminating in a daily Pushbullet report at 00:00 Europe/Istanbul.

**Architecture:** A single Python process organized into small, focused modules (data, portfolio, strategies, engine, storage, reporting, notifier, scheduler) wired together in `main.py`. Each of the 5 agents pairs one strategy implementation with its own `Portfolio` instance; the `SimulationEngine` ties strategies + portfolios + market data + persistence together on an hourly tick, isolating failures per agent. SQLite persists all state so the process can restart without losing simulated history. APScheduler drives both the hourly trading tick and the daily report job.

**Tech Stack:** Python 3.11+, `requests` (Binance REST + Pushbullet REST notifications), `pandas` (indicators/features), `scikit-learn` (ML strategy), `APScheduler` (scheduling), `python-dotenv` (config), `sqlite3` (stdlib, persistence), `pytest` (testing).

## Global Constraints

- Watchlist (shared by all agents): `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT`
- Each of the 5 agents starts with an independent virtual balance of $10,000 (not a shared pool)
- Signal timeframe: 1-hour candles
- Simulated trading fee: 0.1% of trade notional on every fill (matches Binance spot taker fee)
- Max position size: 25% of portfolio value per symbol
- Stop-loss: 5% below a position's average entry price, checked every tick before new signals are evaluated
- No leverage, spot-only simulation, no real orders ever placed
- Data source: Binance public REST API (`https://api.binance.com`), no API key required
- Daily report fires at 00:00 `Europe/Istanbul`, delivered as a single Pushbullet Note push
- No live-network calls in automated tests — `MarketDataClient` and `PushbulletNotifier` are mocked/faked

---

### Task 1: Project Scaffolding & Config

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `src/__init__.py`, `src/config.py`
- Create: `src/data/__init__.py`, `src/portfolio/__init__.py`, `src/strategies/__init__.py`, `src/engine/__init__.py`, `src/scheduler/__init__.py`, `src/reporting/__init__.py`, `src/notifier/__init__.py`, `src/storage/__init__.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config` class (instantiated as `Config()`) with attributes `WATCHLIST: list[str]`, `INITIAL_BALANCE: float`, `DB_PATH: str`, `PUSHBULLET_TOKEN: str`, `TIMEZONE: str`

- [ ] **Step 1: Create `requirements.txt`**

```
requests==2.31.0
pandas==2.2.0
scikit-learn==1.4.0
APScheduler==3.10.4
python-dotenv==1.0.1
pytest==8.0.0
```

- [ ] **Step 2: Create `pytest.ini`**

```ini
[pytest]
pythonpath = .
testpaths = tests
```

- [ ] **Step 3: Create `.env.example`**

```
PUSHBULLET_TOKEN=your-pushbullet-access-token-here
DB_PATH=trade_bot_sim.db
```

- [ ] **Step 4: Create `.gitignore`**

```
__pycache__/
*.pyc
.env
*.db
venv/
```

- [ ] **Step 5: Create empty `__init__.py` files**

Create each of these as an empty file:
- `src/__init__.py`
- `src/data/__init__.py`
- `src/portfolio/__init__.py`
- `src/strategies/__init__.py`
- `src/engine/__init__.py`
- `src/scheduler/__init__.py`
- `src/reporting/__init__.py`
- `src/notifier/__init__.py`
- `src/storage/__init__.py`

Also create `tests/__init__.py` (empty).

- [ ] **Step 6: Write the failing test for Config**

`tests/test_config.py`:

```python
from src.config import Config


def test_config_defaults(monkeypatch):
    monkeypatch.delenv("DB_PATH", raising=False)
    monkeypatch.delenv("PUSHBULLET_TOKEN", raising=False)
    config = Config()
    assert config.WATCHLIST == ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
    assert config.INITIAL_BALANCE == 10_000.0
    assert config.DB_PATH == "trade_bot_sim.db"
    assert config.TIMEZONE == "Europe/Istanbul"


def test_config_env_override(monkeypatch):
    monkeypatch.setenv("DB_PATH", "/tmp/custom.db")
    monkeypatch.setenv("PUSHBULLET_TOKEN", "abc123")
    config = Config()
    assert config.DB_PATH == "/tmp/custom.db"
    assert config.PUSHBULLET_TOKEN == "abc123"
```

- [ ] **Step 7: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.config'`

- [ ] **Step 8: Write `src/config.py`**

```python
import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    def __init__(self):
        self.WATCHLIST = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
        self.INITIAL_BALANCE = 10_000.0
        self.DB_PATH = os.getenv("DB_PATH", "trade_bot_sim.db")
        self.PUSHBULLET_TOKEN = os.getenv("PUSHBULLET_TOKEN", "")
        self.TIMEZONE = "Europe/Istanbul"
```

- [ ] **Step 9: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (2 tests)

- [ ] **Step 10: Install dependencies**

Run: `pip install -r requirements.txt`

- [ ] **Step 11: Commit**

```bash
git add requirements.txt pytest.ini .env.example .gitignore src tests
git commit -m "chore: project scaffolding and config"
```

---

### Task 2: Portfolio (core money math + state serialization)

**Files:**
- Create: `src/portfolio/portfolio.py`
- Test: `tests/portfolio/test_portfolio.py`
- Create: `tests/portfolio/__init__.py` (empty)

**Interfaces:**
- Consumes: nothing (pure, in-memory logic)
- Produces: `Position` dataclass (`symbol: str`, `quantity: float`, `avg_entry_price: float`); `Portfolio` class with `Portfolio(initial_cash: float)`, `.cash`, `.positions: dict[str, Position]`, `.trade_log: list[dict]`, `.buy(symbol, price, cash_amount) -> dict`, `.sell(symbol, price, quantity) -> dict`, `.total_value(current_prices: dict[str, float]) -> float`, `.total_pnl(current_prices) -> tuple[float, float]`, `.to_state() -> dict`, `Portfolio.from_state(initial_cash, state) -> Portfolio`

- [ ] **Step 1: Write the failing tests**

`tests/portfolio/test_portfolio.py`:

```python
import pytest

from src.portfolio.portfolio import Portfolio


def test_buy_reduces_cash_and_creates_position():
    p = Portfolio(10_000.0)
    p.buy("BTCUSDT", price=100.0, cash_amount=1000.0)
    assert p.cash == pytest.approx(9000.0)
    assert "BTCUSDT" in p.positions
    assert p.positions["BTCUSDT"].quantity == pytest.approx(9.9)  # (1000 - 0.1% fee) / 100


def test_buy_applies_fee():
    p = Portfolio(10_000.0)
    trade = p.buy("BTCUSDT", price=100.0, cash_amount=1000.0)
    assert trade["fee"] == pytest.approx(1.0)


def test_buy_insufficient_cash_raises():
    p = Portfolio(100.0)
    with pytest.raises(ValueError):
        p.buy("BTCUSDT", price=100.0, cash_amount=1000.0)


def test_buy_averages_entry_price_on_second_buy():
    p = Portfolio(10_000.0)
    p.buy("BTCUSDT", price=100.0, cash_amount=1000.0)
    p.buy("BTCUSDT", price=200.0, cash_amount=1000.0)
    pos = p.positions["BTCUSDT"]
    # first buy: 9.9 @ 100, second buy: 4.95 @ 200
    expected_qty = 9.9 + 4.95
    expected_avg = (100.0 * 9.9 + 200.0 * 4.95) / expected_qty
    assert pos.quantity == pytest.approx(expected_qty)
    assert pos.avg_entry_price == pytest.approx(expected_avg)


def test_sell_increases_cash_and_reduces_position():
    p = Portfolio(10_000.0)
    p.buy("BTCUSDT", price=100.0, cash_amount=1000.0)
    qty = p.positions["BTCUSDT"].quantity
    p.sell("BTCUSDT", price=150.0, quantity=qty)
    assert "BTCUSDT" not in p.positions
    assert p.cash > 9000.0


def test_sell_insufficient_position_raises():
    p = Portfolio(10_000.0)
    with pytest.raises(ValueError):
        p.sell("BTCUSDT", price=100.0, quantity=1.0)


def test_sell_partial_keeps_remaining_position():
    p = Portfolio(10_000.0)
    p.buy("BTCUSDT", price=100.0, cash_amount=1000.0)
    qty = p.positions["BTCUSDT"].quantity
    p.sell("BTCUSDT", price=150.0, quantity=qty / 2)
    assert p.positions["BTCUSDT"].quantity == pytest.approx(qty / 2)


def test_sell_records_entry_price_and_pnl():
    p = Portfolio(10_000.0)
    p.buy("BTCUSDT", price=100.0, cash_amount=1000.0)
    qty = p.positions["BTCUSDT"].quantity
    trade = p.sell("BTCUSDT", price=150.0, quantity=qty)
    assert trade["entry_price"] == pytest.approx(100.0)
    assert trade["pnl"] == pytest.approx((150.0 - 100.0) * qty - trade["fee"])


def test_total_value_with_open_position():
    p = Portfolio(10_000.0)
    p.buy("BTCUSDT", price=100.0, cash_amount=1000.0)
    value = p.total_value({"BTCUSDT": 200.0})
    qty = p.positions["BTCUSDT"].quantity
    assert value == pytest.approx(p.cash + qty * 200.0)


def test_total_pnl_positive_and_negative():
    p = Portfolio(10_000.0)
    pnl_abs, pnl_pct = p.total_pnl({})
    assert pnl_abs == pytest.approx(0.0)
    assert pnl_pct == pytest.approx(0.0)

    p.buy("BTCUSDT", price=100.0, cash_amount=1000.0)
    pnl_abs, pnl_pct = p.total_pnl({"BTCUSDT": 50.0})
    assert pnl_abs < 0
    assert pnl_pct < 0


def test_to_state_and_from_state_round_trip():
    p = Portfolio(10_000.0)
    p.buy("BTCUSDT", price=100.0, cash_amount=1000.0)
    state = p.to_state()
    restored = Portfolio.from_state(10_000.0, state)
    assert restored.cash == pytest.approx(p.cash)
    assert restored.positions["BTCUSDT"].quantity == pytest.approx(
        p.positions["BTCUSDT"].quantity
    )
    assert restored.positions["BTCUSDT"].avg_entry_price == pytest.approx(
        p.positions["BTCUSDT"].avg_entry_price
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/portfolio/test_portfolio.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.portfolio.portfolio'`

- [ ] **Step 3: Write `src/portfolio/portfolio.py`**

```python
from dataclasses import dataclass

FEE_RATE = 0.001  # 0.1% simulated Binance spot taker fee


@dataclass
class Position:
    symbol: str
    quantity: float
    avg_entry_price: float


class Portfolio:
    def __init__(self, initial_cash: float):
        self.cash = initial_cash
        self.initial_cash = initial_cash
        self.positions: dict[str, Position] = {}
        self.trade_log: list[dict] = []

    def buy(self, symbol: str, price: float, cash_amount: float) -> dict:
        if cash_amount > self.cash:
            raise ValueError("Insufficient cash")
        fee = cash_amount * FEE_RATE
        net_cash = cash_amount - fee
        quantity = net_cash / price

        self.cash -= cash_amount
        if symbol in self.positions:
            pos = self.positions[symbol]
            total_qty = pos.quantity + quantity
            pos.avg_entry_price = (
                pos.avg_entry_price * pos.quantity + price * quantity
            ) / total_qty
            pos.quantity = total_qty
        else:
            self.positions[symbol] = Position(symbol, quantity, price)

        trade = {
            "side": "BUY",
            "symbol": symbol,
            "price": price,
            "quantity": quantity,
            "fee": fee,
        }
        self.trade_log.append(trade)
        return trade

    def sell(self, symbol: str, price: float, quantity: float) -> dict:
        if symbol not in self.positions or self.positions[symbol].quantity < quantity:
            raise ValueError("Insufficient position")

        pos = self.positions[symbol]
        entry_price = pos.avg_entry_price
        gross = quantity * price
        fee = gross * FEE_RATE
        net = gross - fee
        pnl = (price - entry_price) * quantity - fee

        self.cash += net
        pos.quantity -= quantity
        if pos.quantity <= 1e-12:
            del self.positions[symbol]

        trade = {
            "side": "SELL",
            "symbol": symbol,
            "price": price,
            "quantity": quantity,
            "fee": fee,
            "entry_price": entry_price,
            "pnl": pnl,
        }
        self.trade_log.append(trade)
        return trade

    def total_value(self, current_prices: dict[str, float]) -> float:
        value = self.cash
        for symbol, pos in self.positions.items():
            value += pos.quantity * current_prices.get(symbol, pos.avg_entry_price)
        return value

    def total_pnl(self, current_prices: dict[str, float]) -> tuple[float, float]:
        value = self.total_value(current_prices)
        pnl_abs = value - self.initial_cash
        pnl_pct = (pnl_abs / self.initial_cash) * 100
        return pnl_abs, pnl_pct

    def to_state(self) -> dict:
        return {
            "cash": self.cash,
            "positions": {
                symbol: {
                    "quantity": pos.quantity,
                    "avg_entry_price": pos.avg_entry_price,
                }
                for symbol, pos in self.positions.items()
            },
        }

    @classmethod
    def from_state(cls, initial_cash: float, state: dict) -> "Portfolio":
        portfolio = cls(initial_cash)
        portfolio.cash = state["cash"]
        portfolio.positions = {
            symbol: Position(symbol, data["quantity"], data["avg_entry_price"])
            for symbol, data in state["positions"].items()
        }
        return portfolio
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/portfolio/test_portfolio.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add src/portfolio tests/portfolio
git commit -m "feat: add Portfolio with buy/sell/pnl and state serialization"
```

---

### Task 3: Storage Layer (SQLite persistence)

**Files:**
- Create: `src/storage/db.py`
- Test: `tests/storage/test_db.py`
- Create: `tests/storage/__init__.py` (empty)

**Interfaces:**
- Consumes: plain dicts shaped like `Portfolio.to_state()` output (`{"cash": float, "positions": {symbol: {"quantity": float, "avg_entry_price": float}}}`)
- Produces: `init_db(db_path: str) -> sqlite3.Connection`, `save_portfolio_state(conn, agent_name, cash, positions) -> None`, `load_portfolio_state(conn, agent_name) -> dict | None`, `log_trade(conn, agent_name, symbol, side, quantity, price, fee, timestamp, entry_price=None, pnl=None) -> None`, `get_trades_since(conn, agent_name, since_timestamp) -> list[dict]`, `save_daily_report(conn, report_date, report_text) -> None`, `save_balance_snapshot(conn, agent_name, snapshot_date, balance) -> None`, `get_previous_balance_snapshot(conn, agent_name, before_date) -> float | None`

- [ ] **Step 1: Write the failing tests**

`tests/storage/test_db.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/storage/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.storage.db'`

- [ ] **Step 3: Write `src/storage/db.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/storage/test_db.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add src/storage tests/storage
git commit -m "feat: add SQLite storage layer for portfolios, trades, reports"
```

---

### Task 4: Market Data Client (Binance REST wrapper)

**Files:**
- Create: `src/data/binance_client.py`
- Test: `tests/data/test_binance_client.py`
- Create: `tests/data/__init__.py` (empty)

**Interfaces:**
- Produces: `MarketDataError` exception; `MarketDataClient(base_url=..., max_retries=3, retry_delay_seconds=2.0)` with `.get_klines(symbol: str, interval: str = "1h", limit: int = 100) -> list[dict]` (each dict has keys `open_time, open, high, low, close, volume`) and `.get_current_price(symbol: str) -> float`

- [ ] **Step 1: Write the failing tests**

`tests/data/test_binance_client.py`:

```python
from unittest.mock import Mock, patch

import pytest
import requests

from src.data.binance_client import MarketDataClient, MarketDataError


def make_response(json_data, status_ok=True):
    resp = Mock()
    resp.json.return_value = json_data
    if status_ok:
        resp.raise_for_status.return_value = None
    else:
        resp.raise_for_status.side_effect = requests.RequestException("boom")
    return resp


@patch("src.data.binance_client.requests.get")
def test_get_klines_parses_response(mock_get):
    raw = [[1690000000000, "100.0", "110.0", "90.0", "105.0", "12.5", 0, 0, 0, 0, 0, 0]]
    mock_get.return_value = make_response(raw)

    client = MarketDataClient()
    candles = client.get_klines("BTCUSDT", interval="1h", limit=1)

    assert candles == [
        {
            "open_time": 1690000000000,
            "open": 100.0,
            "high": 110.0,
            "low": 90.0,
            "close": 105.0,
            "volume": 12.5,
        }
    ]
    mock_get.assert_called_once()
    _, kwargs = mock_get.call_args
    assert kwargs["params"] == {"symbol": "BTCUSDT", "interval": "1h", "limit": 1}


@patch("src.data.binance_client.requests.get")
def test_get_current_price_parses_response(mock_get):
    mock_get.return_value = make_response({"symbol": "BTCUSDT", "price": "123.45"})

    client = MarketDataClient()
    price = client.get_current_price("BTCUSDT")

    assert price == 123.45


@patch("src.data.binance_client.time.sleep", return_value=None)
@patch("src.data.binance_client.requests.get")
def test_get_klines_retries_on_failure_then_succeeds(mock_get, mock_sleep):
    failing_resp = make_response(None, status_ok=False)
    succeeding_resp = make_response(
        [[1690000000000, "1", "2", "0.5", "1.5", "10", 0, 0, 0, 0, 0, 0]]
    )
    mock_get.side_effect = [failing_resp, succeeding_resp]

    client = MarketDataClient(max_retries=3, retry_delay_seconds=0)
    candles = client.get_klines("BTCUSDT")

    assert len(candles) == 1
    assert mock_get.call_count == 2


@patch("src.data.binance_client.time.sleep", return_value=None)
@patch("src.data.binance_client.requests.get")
def test_get_klines_raises_after_max_retries(mock_get, mock_sleep):
    mock_get.return_value = make_response(None, status_ok=False)

    client = MarketDataClient(max_retries=2, retry_delay_seconds=0)
    with pytest.raises(MarketDataError):
        client.get_klines("BTCUSDT")

    assert mock_get.call_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/data/test_binance_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.data.binance_client'`

- [ ] **Step 3: Write `src/data/binance_client.py`**

```python
import time

import requests

BASE_URL = "https://api.binance.com"


class MarketDataError(Exception):
    pass


class MarketDataClient:
    def __init__(self, base_url: str = BASE_URL, max_retries: int = 3, retry_delay_seconds: float = 2.0):
        self.base_url = base_url
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds

    def _get(self, path: str, params: dict):
        last_exc = None
        for _ in range(self.max_retries):
            try:
                resp = requests.get(f"{self.base_url}{path}", params=params, timeout=10)
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(self.retry_delay_seconds)
        raise MarketDataError(f"Failed to fetch {path} after {self.max_retries} attempts: {last_exc}")

    def get_klines(self, symbol: str, interval: str = "1h", limit: int = 100) -> list[dict]:
        raw = self._get("/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit})
        return [
            {
                "open_time": row[0],
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            }
            for row in raw
        ]

    def get_current_price(self, symbol: str) -> float:
        raw = self._get("/api/v3/ticker/price", {"symbol": symbol})
        return float(raw["price"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/data/test_binance_client.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/data tests/data
git commit -m "feat: add Binance market data client with retry/backoff"
```

---

### Task 5: Strategy Base Interface

**Files:**
- Create: `src/strategies/base.py`
- Test: `tests/strategies/test_base.py`
- Create: `tests/strategies/__init__.py` (empty)

**Interfaces:**
- Produces: `Action` enum (`BUY`, `SELL`, `HOLD`); `Signal` dataclass (`action: Action`, `symbol: str`, `confidence: float = 1.0`); `BaseStrategy` class with `.name: str` and `.generate_signal(symbol: str, candles: list[dict]) -> Signal` (raises `NotImplementedError`)
- Note: `candles` is always the list of dicts produced by `MarketDataClient.get_klines` (Task 4), ordered oldest to newest.

- [ ] **Step 1: Write the failing test**

`tests/strategies/test_base.py`:

```python
import pytest

from src.strategies.base import BaseStrategy


def test_base_strategy_raises_not_implemented():
    strategy = BaseStrategy()
    with pytest.raises(NotImplementedError):
        strategy.generate_signal("BTCUSDT", [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/strategies/test_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.strategies.base'`

- [ ] **Step 3: Write `src/strategies/base.py`**

```python
from dataclasses import dataclass
from enum import Enum


class Action(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class Signal:
    action: Action
    symbol: str
    confidence: float = 1.0


class BaseStrategy:
    name: str = "base"

    def generate_signal(self, symbol: str, candles: list[dict]) -> Signal:
        raise NotImplementedError
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/strategies/test_base.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add src/strategies/base.py tests/strategies/test_base.py tests/strategies/__init__.py
git commit -m "feat: add strategy base interface and Signal/Action types"
```

---

### Task 6: Technical Indicator Helpers

**Files:**
- Create: `src/strategies/indicators.py`
- Test: `tests/strategies/test_indicators.py`

**Interfaces:**
- Produces: `ema(values: list[float], period: int) -> pandas.Series`, `rsi(values: list[float], period: int = 14) -> pandas.Series`, `bollinger_bands(values: list[float], period: int = 20, num_std: float = 2.0) -> tuple[Series, Series, Series]` (upper, mid, lower), `macd(values: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[Series, Series]` (macd_line, signal_line)

- [ ] **Step 1: Write the failing tests**

`tests/strategies/test_indicators.py`:

```python
import pytest

from src.strategies.indicators import bollinger_bands, ema, macd, rsi


def test_ema_of_constant_series_equals_constant():
    result = ema([10.0] * 5, period=3)
    assert result.iloc[-1] == pytest.approx(10.0)


def test_ema_reacts_to_recent_values():
    result = ema([10.0] * 10 + [20.0] * 5, period=3)
    assert result.iloc[-1] > 10.0
    assert result.iloc[-1] < 20.0


def test_rsi_of_strictly_increasing_series_is_high():
    values = [float(i) for i in range(1, 30)]
    result = rsi(values, period=14)
    assert result.iloc[-1] > 90


def test_rsi_of_strictly_decreasing_series_is_low():
    values = [float(i) for i in range(30, 1, -1)]
    result = rsi(values, period=14)
    assert result.iloc[-1] < 10


def test_bollinger_bands_mid_equals_rolling_mean():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    upper, mid, lower = bollinger_bands(values, period=5, num_std=2.0)
    assert mid.iloc[-1] == pytest.approx(3.0)
    assert upper.iloc[-1] > mid.iloc[-1]
    assert lower.iloc[-1] < mid.iloc[-1]


def test_macd_line_is_difference_of_emas():
    values = [float(i) for i in range(1, 40)]
    macd_line, signal_line = macd(values, fast=5, slow=10, signal=3)
    expected = ema(values, 5).iloc[-1] - ema(values, 10).iloc[-1]
    assert macd_line.iloc[-1] == pytest.approx(expected)
    assert len(signal_line) == len(macd_line)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/strategies/test_indicators.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.strategies.indicators'`

- [ ] **Step 3: Write `src/strategies/indicators.py`**

```python
import pandas as pd


def ema(values: list[float], period: int) -> pd.Series:
    return pd.Series(values).ewm(span=period, adjust=False).mean()


def rsi(values: list[float], period: int = 14) -> pd.Series:
    series = pd.Series(values)
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-12)
    return 100 - (100 / (1 + rs))


def bollinger_bands(
    values: list[float], period: int = 20, num_std: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    series = pd.Series(values)
    mid = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return upper, mid, lower


def macd(
    values: list[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series]:
    fast_ema = ema(values, fast)
    slow_ema = ema(values, slow)
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/strategies/test_indicators.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/strategies/indicators.py tests/strategies/test_indicators.py
git commit -m "feat: add EMA/RSI/Bollinger/MACD indicator helpers"
```

---

### Task 7: Trend Follower Strategy

**Files:**
- Create: `src/strategies/trend_follower.py`
- Test: `tests/strategies/test_trend_follower.py`

**Interfaces:**
- Consumes: `BaseStrategy`, `Signal`, `Action` (Task 5); `ema` (Task 6)
- Produces: `TrendFollowerStrategy` class, `name = "trend_follower"`, implements `generate_signal(symbol, candles) -> Signal` (EMA(9)/EMA(21) crossover)

- [ ] **Step 1: Write the failing tests**

`tests/strategies/test_trend_follower.py`:

```python
from src.strategies.base import Action
from src.strategies.trend_follower import TrendFollowerStrategy


def make_candles(closes: list[float]) -> list[dict]:
    return [{"close": c, "open": c, "high": c, "low": c, "volume": 1.0, "open_time": i} for i, c in enumerate(closes)]


def test_not_enough_data_returns_hold():
    strategy = TrendFollowerStrategy()
    signal = strategy.generate_signal("BTCUSDT", make_candles([100.0] * 5))
    assert signal.action == Action.HOLD


def test_bullish_crossover_returns_buy():
    # Flat then a sharp recent upswing pulls the fast EMA above the slow EMA
    closes = [100.0] * 25 + [130.0, 135.0, 140.0]
    strategy = TrendFollowerStrategy()
    signal = strategy.generate_signal("BTCUSDT", make_candles(closes))
    assert signal.action == Action.BUY
    assert signal.symbol == "BTCUSDT"


def test_bearish_crossover_returns_sell():
    closes = [100.0] * 25 + [70.0, 65.0, 60.0]
    strategy = TrendFollowerStrategy()
    signal = strategy.generate_signal("BTCUSDT", make_candles(closes))
    assert signal.action == Action.SELL


def test_flat_series_returns_hold():
    strategy = TrendFollowerStrategy()
    signal = strategy.generate_signal("BTCUSDT", make_candles([100.0] * 30))
    assert signal.action == Action.HOLD
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/strategies/test_trend_follower.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.strategies.trend_follower'`

- [ ] **Step 3: Write `src/strategies/trend_follower.py`**

```python
from .base import Action, BaseStrategy, Signal
from .indicators import ema


class TrendFollowerStrategy(BaseStrategy):
    name = "trend_follower"

    def generate_signal(self, symbol: str, candles: list[dict]) -> Signal:
        closes = [c["close"] for c in candles]
        if len(closes) < 22:
            return Signal(Action.HOLD, symbol)

        ema_fast = ema(closes, 9)
        ema_slow = ema(closes, 21)
        prev_fast, prev_slow = ema_fast.iloc[-2], ema_slow.iloc[-2]
        curr_fast, curr_slow = ema_fast.iloc[-1], ema_slow.iloc[-1]

        if prev_fast <= prev_slow and curr_fast > curr_slow:
            return Signal(Action.BUY, symbol)
        if prev_fast >= prev_slow and curr_fast < curr_slow:
            return Signal(Action.SELL, symbol)
        return Signal(Action.HOLD, symbol)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/strategies/test_trend_follower.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/strategies/trend_follower.py tests/strategies/test_trend_follower.py
git commit -m "feat: add trend follower strategy (EMA crossover)"
```

---

### Task 8: Mean Reversion Strategy

**Files:**
- Create: `src/strategies/mean_reversion.py`
- Test: `tests/strategies/test_mean_reversion.py`

**Interfaces:**
- Consumes: `BaseStrategy`, `Signal`, `Action` (Task 5); `rsi`, `bollinger_bands` (Task 6)
- Produces: `MeanReversionStrategy` class, `name = "mean_reversion"`, implements `generate_signal(symbol, candles) -> Signal` (RSI(14) + Bollinger(20,2))

- [ ] **Step 1: Write the failing tests**

`tests/strategies/test_mean_reversion.py`:

```python
from src.strategies.base import Action
from src.strategies.mean_reversion import MeanReversionStrategy


def make_candles(closes: list[float]) -> list[dict]:
    return [{"close": c, "open": c, "high": c, "low": c, "volume": 1.0, "open_time": i} for i, c in enumerate(closes)]


def test_not_enough_data_returns_hold():
    strategy = MeanReversionStrategy()
    signal = strategy.generate_signal("BTCUSDT", make_candles([100.0] * 5))
    assert signal.action == Action.HOLD


def test_oversold_dip_returns_buy():
    closes = [100.0] * 20 + [90.0, 80.0, 70.0]
    strategy = MeanReversionStrategy()
    signal = strategy.generate_signal("BTCUSDT", make_candles(closes))
    assert signal.action == Action.BUY


def test_overbought_spike_returns_sell():
    closes = [100.0] * 20 + [110.0, 120.0, 130.0]
    strategy = MeanReversionStrategy()
    signal = strategy.generate_signal("BTCUSDT", make_candles(closes))
    assert signal.action == Action.SELL


def test_stable_series_returns_hold():
    strategy = MeanReversionStrategy()
    signal = strategy.generate_signal("BTCUSDT", make_candles([100.0] * 25))
    assert signal.action == Action.HOLD
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/strategies/test_mean_reversion.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.strategies.mean_reversion'`

- [ ] **Step 3: Write `src/strategies/mean_reversion.py`**

```python
from .base import Action, BaseStrategy, Signal
from .indicators import bollinger_bands, rsi


class MeanReversionStrategy(BaseStrategy):
    name = "mean_reversion"

    def generate_signal(self, symbol: str, candles: list[dict]) -> Signal:
        closes = [c["close"] for c in candles]
        if len(closes) < 21:
            return Signal(Action.HOLD, symbol)

        rsi_values = rsi(closes, 14)
        upper, _, lower = bollinger_bands(closes, 20, 2.0)

        curr_rsi = rsi_values.iloc[-1]
        curr_close = closes[-1]

        if curr_rsi < 30 and curr_close <= lower.iloc[-1]:
            return Signal(Action.BUY, symbol)
        if curr_rsi > 70 and curr_close >= upper.iloc[-1]:
            return Signal(Action.SELL, symbol)
        return Signal(Action.HOLD, symbol)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/strategies/test_mean_reversion.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/strategies/mean_reversion.py tests/strategies/test_mean_reversion.py
git commit -m "feat: add mean reversion strategy (RSI + Bollinger Bands)"
```

---

### Task 9: Momentum Breakout Strategy

**Files:**
- Create: `src/strategies/momentum_breakout.py`
- Test: `tests/strategies/test_momentum_breakout.py`

**Interfaces:**
- Consumes: `BaseStrategy`, `Signal`, `Action` (Task 5); `macd` (Task 6)
- Produces: `MomentumBreakoutStrategy` class, `name = "momentum_breakout"`, implements `generate_signal(symbol, candles) -> Signal` (MACD crossover + volume confirmation)

- [ ] **Step 1: Write the failing tests**

`tests/strategies/test_momentum_breakout.py`:

```python
from src.strategies.base import Action
from src.strategies.momentum_breakout import MomentumBreakoutStrategy


def make_candles(closes: list[float], volumes: list[float]) -> list[dict]:
    return [
        {"close": c, "open": c, "high": c, "low": c, "volume": v, "open_time": i}
        for i, (c, v) in enumerate(zip(closes, volumes))
    ]


def test_not_enough_data_returns_hold():
    strategy = MomentumBreakoutStrategy()
    candles = make_candles([100.0] * 5, [10.0] * 5)
    signal = strategy.generate_signal("BTCUSDT", candles)
    assert signal.action == Action.HOLD


def test_bullish_macd_cross_with_volume_confirmation_returns_buy():
    closes = [100.0] * 30 + [110.0, 120.0, 130.0]
    volumes = [10.0] * 30 + [50.0, 50.0, 50.0]
    strategy = MomentumBreakoutStrategy()
    signal = strategy.generate_signal("BTCUSDT", make_candles(closes, volumes))
    assert signal.action == Action.BUY


def test_bullish_macd_cross_without_volume_confirmation_returns_hold():
    closes = [100.0] * 30 + [110.0, 120.0, 130.0]
    volumes = [10.0] * 33  # no volume spike
    strategy = MomentumBreakoutStrategy()
    signal = strategy.generate_signal("BTCUSDT", make_candles(closes, volumes))
    assert signal.action == Action.HOLD


def test_bearish_macd_cross_returns_sell():
    closes = [100.0] * 30 + [90.0, 80.0, 70.0]
    volumes = [10.0] * 33
    strategy = MomentumBreakoutStrategy()
    signal = strategy.generate_signal("BTCUSDT", make_candles(closes, volumes))
    assert signal.action == Action.SELL
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/strategies/test_momentum_breakout.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.strategies.momentum_breakout'`

- [ ] **Step 3: Write `src/strategies/momentum_breakout.py`**

```python
from .base import Action, BaseStrategy, Signal
from .indicators import macd


class MomentumBreakoutStrategy(BaseStrategy):
    name = "momentum_breakout"

    def generate_signal(self, symbol: str, candles: list[dict]) -> Signal:
        closes = [c["close"] for c in candles]
        volumes = [c["volume"] for c in candles]
        if len(closes) < 27:
            return Signal(Action.HOLD, symbol)

        macd_line, signal_line = macd(closes)
        avg_volume = sum(volumes[-20:]) / 20
        curr_volume = volumes[-1]

        prev_macd, prev_signal = macd_line.iloc[-2], signal_line.iloc[-2]
        curr_macd, curr_signal = macd_line.iloc[-1], signal_line.iloc[-1]
        volume_confirmed = curr_volume > avg_volume

        if prev_macd <= prev_signal and curr_macd > curr_signal and volume_confirmed:
            return Signal(Action.BUY, symbol)
        if prev_macd >= prev_signal and curr_macd < curr_signal:
            return Signal(Action.SELL, symbol)
        return Signal(Action.HOLD, symbol)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/strategies/test_momentum_breakout.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/strategies/momentum_breakout.py tests/strategies/test_momentum_breakout.py
git commit -m "feat: add momentum breakout strategy (MACD + volume)"
```

---

### Task 10: Grid Trader Strategy

**Files:**
- Create: `src/strategies/grid_trader.py`
- Test: `tests/strategies/test_grid_trader.py`

**Interfaces:**
- Consumes: `BaseStrategy`, `Signal`, `Action` (Task 5)
- Produces: `GridTraderStrategy` class, `name = "grid_trader"`, `GridTraderStrategy(grid_step_pct: float = 0.02)`, implements `generate_signal(symbol, candles) -> Signal`. Stateful per symbol (in-memory reference price + grid level); this internal state is not persisted — on process restart the grid simply re-centers on the current price, which is an accepted simplification since only `Portfolio` state requires durability (see spec section 5).

- [ ] **Step 1: Write the failing tests**

`tests/strategies/test_grid_trader.py`:

```python
from src.strategies.base import Action
from src.strategies.grid_trader import GridTraderStrategy


def make_candles(closes: list[float]) -> list[dict]:
    return [{"close": c, "open": c, "high": c, "low": c, "volume": 1.0, "open_time": i} for i, c in enumerate(closes)]


def test_first_call_sets_reference_and_holds():
    strategy = GridTraderStrategy(grid_step_pct=0.02)
    signal = strategy.generate_signal("BTCUSDT", make_candles([100.0]))
    assert signal.action == Action.HOLD


def test_price_drop_by_one_grid_step_returns_buy():
    strategy = GridTraderStrategy(grid_step_pct=0.02)
    strategy.generate_signal("BTCUSDT", make_candles([100.0]))
    signal = strategy.generate_signal("BTCUSDT", make_candles([100.0, 97.0]))
    assert signal.action == Action.BUY


def test_price_rise_after_drop_returns_sell():
    strategy = GridTraderStrategy(grid_step_pct=0.02)
    strategy.generate_signal("BTCUSDT", make_candles([100.0]))
    strategy.generate_signal("BTCUSDT", make_candles([100.0, 97.0]))
    signal = strategy.generate_signal("BTCUSDT", make_candles([100.0, 97.0, 100.0]))
    assert signal.action == Action.SELL


def test_no_grid_step_move_returns_hold():
    strategy = GridTraderStrategy(grid_step_pct=0.02)
    strategy.generate_signal("BTCUSDT", make_candles([100.0]))
    signal = strategy.generate_signal("BTCUSDT", make_candles([100.0, 100.5]))
    assert signal.action == Action.HOLD


def test_tracks_state_independently_per_symbol():
    strategy = GridTraderStrategy(grid_step_pct=0.02)
    strategy.generate_signal("BTCUSDT", make_candles([100.0]))
    strategy.generate_signal("ETHUSDT", make_candles([50.0]))
    signal_btc = strategy.generate_signal("BTCUSDT", make_candles([100.0, 97.0]))
    signal_eth = strategy.generate_signal("ETHUSDT", make_candles([50.0, 50.1]))
    assert signal_btc.action == Action.BUY
    assert signal_eth.action == Action.HOLD
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/strategies/test_grid_trader.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.strategies.grid_trader'`

- [ ] **Step 3: Write `src/strategies/grid_trader.py`**

```python
from .base import Action, BaseStrategy, Signal


class GridTraderStrategy(BaseStrategy):
    name = "grid_trader"

    def __init__(self, grid_step_pct: float = 0.02):
        self.grid_step_pct = grid_step_pct
        self.reference_price: dict[str, float] = {}
        self.last_level: dict[str, int] = {}

    def generate_signal(self, symbol: str, candles: list[dict]) -> Signal:
        if not candles:
            return Signal(Action.HOLD, symbol)
        price = candles[-1]["close"]

        if symbol not in self.reference_price:
            self.reference_price[symbol] = price
            self.last_level[symbol] = 0
            return Signal(Action.HOLD, symbol)

        ref = self.reference_price[symbol]
        current_level = round((price - ref) / (ref * self.grid_step_pct))
        prev_level = self.last_level[symbol]
        self.last_level[symbol] = current_level

        if current_level < prev_level:
            return Signal(Action.BUY, symbol)
        if current_level > prev_level:
            return Signal(Action.SELL, symbol)
        return Signal(Action.HOLD, symbol)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/strategies/test_grid_trader.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/strategies/grid_trader.py tests/strategies/test_grid_trader.py
git commit -m "feat: add grid trader strategy"
```

---

### Task 11: ML Predictor Strategy

**Files:**
- Create: `src/strategies/ml_predictor.py`
- Test: `tests/strategies/test_ml_predictor.py`

**Interfaces:**
- Consumes: `BaseStrategy`, `Signal`, `Action` (Task 5); `rsi`, `macd` (Task 6)
- Produces: `MLPredictorStrategy` class, `name = "ml_predictor"`, implements `generate_signal(symbol, candles) -> Signal`. Trains a `GradientBoostingClassifier` on rolling engineered features, retrains when the cached model is missing or older than `RETRAIN_INTERVAL_SECONDS`.

- [ ] **Step 1: Write the failing tests**

`tests/strategies/test_ml_predictor.py`:

```python
import time

from src.strategies.base import Action
from src.strategies.ml_predictor import MLPredictorStrategy


def make_trending_candles(n: int, start: float = 100.0, step: float = 1.0) -> list[dict]:
    closes = [start + i * step for i in range(n)]
    return [
        {"close": c, "open": c, "high": c + 0.5, "low": c - 0.5, "volume": 10.0 + i % 5, "open_time": i}
        for i, c in enumerate(closes)
    ]


def test_not_enough_data_returns_hold():
    strategy = MLPredictorStrategy()
    signal = strategy.generate_signal("BTCUSDT", make_trending_candles(10))
    assert signal.action == Action.HOLD


def test_trains_model_on_first_sufficient_call():
    strategy = MLPredictorStrategy()
    candles = make_trending_candles(90)
    strategy.generate_signal("BTCUSDT", candles)
    assert strategy.model is not None


def test_strong_uptrend_produces_buy_with_confidence():
    strategy = MLPredictorStrategy()
    candles = make_trending_candles(90, start=100.0, step=2.0)
    signal = strategy.generate_signal("BTCUSDT", candles)
    assert signal.action == Action.BUY
    assert signal.confidence >= 0.6


def test_does_not_retrain_within_interval(monkeypatch):
    strategy = MLPredictorStrategy()
    candles = make_trending_candles(90)
    strategy.generate_signal("BTCUSDT", candles)
    first_trained_at = strategy.last_trained_at

    monkeypatch.setattr(time, "time", lambda: first_trained_at + 10)
    strategy.generate_signal("BTCUSDT", candles)
    assert strategy.last_trained_at == first_trained_at


def test_retrains_after_interval_elapses(monkeypatch):
    strategy = MLPredictorStrategy()
    candles = make_trending_candles(90)
    strategy.generate_signal("BTCUSDT", candles)
    first_trained_at = strategy.last_trained_at

    monkeypatch.setattr(time, "time", lambda: first_trained_at + 8 * 24 * 3600)
    strategy.generate_signal("BTCUSDT", candles)
    assert strategy.last_trained_at > first_trained_at
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/strategies/test_ml_predictor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.strategies.ml_predictor'`

- [ ] **Step 3: Write `src/strategies/ml_predictor.py`**

```python
import time

import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier

from .base import Action, BaseStrategy, Signal
from .indicators import macd, rsi

RETRAIN_INTERVAL_SECONDS = 7 * 24 * 3600
MIN_TRAINING_ROWS = 60
CONFIDENCE_THRESHOLD = 0.6
FEATURE_COLUMNS = ["return_1", "rsi", "macd_diff", "volatility", "volume_z"]


class MLPredictorStrategy(BaseStrategy):
    name = "ml_predictor"

    def __init__(self):
        self.model = None
        self.last_trained_at: float = 0.0

    def _build_features(self, candles: list[dict]) -> pd.DataFrame:
        closes = [c["close"] for c in candles]
        volumes = [c["volume"] for c in candles]
        df = pd.DataFrame({"close": closes, "volume": volumes})
        df["return_1"] = df["close"].pct_change()
        df["rsi"] = rsi(closes, 14)
        macd_line, signal_line = macd(closes)
        df["macd_diff"] = macd_line - signal_line
        df["volatility"] = df["return_1"].rolling(10).std()
        volume_std = df["volume"].rolling(20).std().replace(0, 1e-12)
        df["volume_z"] = (df["volume"] - df["volume"].rolling(20).mean()) / volume_std
        return df

    def _train(self, df: pd.DataFrame) -> None:
        target = (df["close"].shift(-1) > df["close"]).astype(int)
        data = pd.concat([df[FEATURE_COLUMNS], target.rename("target")], axis=1).dropna()
        if len(data) < MIN_TRAINING_ROWS:
            self.model = None
            return
        model = GradientBoostingClassifier(n_estimators=50, max_depth=3)
        model.fit(data[FEATURE_COLUMNS], data["target"])
        self.model = model
        self.last_trained_at = time.time()

    def generate_signal(self, symbol: str, candles: list[dict]) -> Signal:
        if len(candles) < MIN_TRAINING_ROWS + 5:
            return Signal(Action.HOLD, symbol)

        df = self._build_features(candles)
        if self.model is None or (time.time() - self.last_trained_at) > RETRAIN_INTERVAL_SECONDS:
            self._train(df)
        if self.model is None:
            return Signal(Action.HOLD, symbol)

        latest = df[FEATURE_COLUMNS].iloc[[-1]]
        if latest.isnull().values.any():
            return Signal(Action.HOLD, symbol)

        proba_up = self.model.predict_proba(latest)[0][1]
        if proba_up >= CONFIDENCE_THRESHOLD:
            return Signal(Action.BUY, symbol, confidence=proba_up)
        if proba_up <= (1 - CONFIDENCE_THRESHOLD):
            return Signal(Action.SELL, symbol, confidence=1 - proba_up)
        return Signal(Action.HOLD, symbol)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/strategies/test_ml_predictor.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/strategies/ml_predictor.py tests/strategies/test_ml_predictor.py
git commit -m "feat: add ML predictor strategy (GradientBoostingClassifier)"
```

---

### Task 12: Simulation Engine

**Files:**
- Create: `src/engine/simulation_engine.py`
- Test: `tests/engine/test_simulation_engine.py`
- Create: `tests/engine/__init__.py` (empty)

**Interfaces:**
- Consumes: `Portfolio` (Task 2); `save_portfolio_state`, `log_trade` (Task 3); `Action` (Task 5); a `market_data_client` duck-typed with `.get_klines(symbol) -> list[dict]` (Task 4)
- Produces: `Agent` class (`Agent(name: str, strategy, portfolio: Portfolio)`); `SimulationEngine` class (`SimulationEngine(agents: list[Agent], market_data_client, storage_conn)`) with `.run_tick(watchlist: list[str]) -> None`
- Constants (module-level, importable): `POSITION_SIZE_PCT = 0.25`, `STOP_LOSS_PCT = 0.05`

- [ ] **Step 1: Write the failing tests**

`tests/engine/test_simulation_engine.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/engine/test_simulation_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.engine.simulation_engine'`

- [ ] **Step 3: Write `src/engine/simulation_engine.py`**

```python
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
        self._apply_stop_losses(agent, prices_by_symbol)

        for symbol in watchlist:
            signal = agent.strategy.generate_signal(symbol, candles_by_symbol[symbol])
            price = prices_by_symbol[symbol]
            if signal.action == Action.BUY:
                self._execute_buy(agent, symbol, price, prices_by_symbol)
            elif signal.action == Action.SELL:
                self._execute_sell(agent, symbol, price)

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
            datetime.datetime.utcnow().isoformat(),
            entry_price=trade.get("entry_price"),
            pnl=trade.get("pnl"),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/engine/test_simulation_engine.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/engine tests/engine
git commit -m "feat: add simulation engine orchestrating agents, risk rules, persistence"
```

---

### Task 13: Report Builder

**Files:**
- Create: `src/reporting/report_builder.py`
- Test: `tests/reporting/test_report_builder.py`
- Create: `tests/reporting/__init__.py` (empty)

**Interfaces:**
- Consumes: `Portfolio` (Task 2) — specifically `.total_value(prices)` and `.total_pnl(prices)`; trade dicts shaped like `get_trades_since` output (Task 3)
- Produces: `compute_agent_report(agent_name, portfolio, current_prices, trades_today, previous_balance) -> dict` (keys: `name, balance, daily_pnl_abs, daily_pnl_pct, total_pnl_abs, total_pnl_pct, open_positions, trades_today, win_rate_pct`); `build_daily_report(agent_reports: list[dict], report_date: str) -> str`

- [ ] **Step 1: Write the failing tests**

`tests/reporting/test_report_builder.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/reporting/test_report_builder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.reporting.report_builder'`

- [ ] **Step 3: Write `src/reporting/report_builder.py`**

```python
from src.portfolio.portfolio import Portfolio


def compute_agent_report(
    agent_name: str,
    portfolio: Portfolio,
    current_prices: dict[str, float],
    trades_today: list[dict],
    previous_balance: float,
) -> dict:
    balance = portfolio.total_value(current_prices)
    total_pnl_abs, total_pnl_pct = portfolio.total_pnl(current_prices)
    daily_pnl_abs = balance - previous_balance
    daily_pnl_pct = (daily_pnl_abs / previous_balance * 100) if previous_balance else 0.0

    sell_trades = [t for t in trades_today if t["side"] == "SELL" and t.get("pnl") is not None]
    wins = [t for t in sell_trades if t["pnl"] > 0]
    win_rate_pct = (len(wins) / len(sell_trades) * 100) if sell_trades else 0.0

    return {
        "name": agent_name,
        "balance": balance,
        "daily_pnl_abs": daily_pnl_abs,
        "daily_pnl_pct": daily_pnl_pct,
        "total_pnl_abs": total_pnl_abs,
        "total_pnl_pct": total_pnl_pct,
        "open_positions": list(portfolio.positions.keys()),
        "trades_today": len(trades_today),
        "win_rate_pct": win_rate_pct,
    }


def build_daily_report(agent_reports: list[dict], report_date: str) -> str:
    ranked = sorted(agent_reports, key=lambda r: r["total_pnl_pct"], reverse=True)
    lines = [f"Trade Bot Sim - Daily Report - {report_date}", ""]
    for rank, r in enumerate(ranked, start=1):
        lines.append(f"#{rank} {r['name']}")
        lines.append(f"  Balance: ${r['balance']:.2f}")
        lines.append(f"  Today: {r['daily_pnl_abs']:+.2f}$ ({r['daily_pnl_pct']:+.2f}%)")
        lines.append(f"  Total: {r['total_pnl_abs']:+.2f}$ ({r['total_pnl_pct']:+.2f}%)")
        lines.append(f"  Open positions: {', '.join(r['open_positions']) or 'none'}")
        lines.append(f"  Trades today: {r['trades_today']} | Win rate: {r['win_rate_pct']:.1f}%")
        lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/reporting/test_report_builder.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/reporting tests/reporting
git commit -m "feat: add daily report builder with agent ranking"
```

---

### Task 14: Pushbullet Notifier

**Implementation note (deviation recorded during execution):** The plan originally called for the `pushbullet.py` PyPI package. During implementation, `pushbullet.py` was found to transitively depend on `python-magic`, which crashes the Python process with a hard access violation on import on Windows (no bundled libmagic DLL) — a real, reproducible segfault, not a cosmetic warning. Since the application only ever needs to send a plain text "note" push (never file/media pushes, the only feature that legitimately needs MIME detection), this task instead calls Pushbullet's REST API directly via `requests` (already a project dependency, and the same pattern already used in `src/data/binance_client.py`). This removes the `python-magic`/native-library dependency entirely and works identically on Windows and the Linux deployment target. `pushbullet.py` must NOT be added to `requirements.txt` — it was already added there in Task 1 and must be removed as part of this task.

**Files:**
- Create: `src/notifier/pushbullet_notifier.py`
- Test: `tests/notifier/test_pushbullet_notifier.py`
- Create: `tests/notifier/__init__.py` (empty)
- Modify: `requirements.txt` (remove the `pushbullet.py==0.12.0` line added in Task 1)

**Interfaces:**
- Produces: `PushbulletNotifier` class (`PushbulletNotifier(access_token: str)`) with `.send_report(title: str, body: str) -> None`. Raises `NotifierError` if the Pushbullet API call fails.

- [ ] **Step 1: Write the failing tests**

`tests/notifier/test_pushbullet_notifier.py`:

```python
from unittest.mock import Mock, patch

import pytest
import requests

from src.notifier.pushbullet_notifier import NotifierError, PushbulletNotifier


def make_response(status_ok=True):
    resp = Mock()
    if status_ok:
        resp.raise_for_status.return_value = None
    else:
        resp.raise_for_status.side_effect = requests.RequestException("boom")
    return resp


@patch("src.notifier.pushbullet_notifier.requests.post")
def test_send_report_posts_note_to_pushbullet_api(mock_post):
    mock_post.return_value = make_response()

    notifier = PushbulletNotifier("fake-token")
    notifier.send_report("Trade Bot Sim - Daily Report", "report body text")

    mock_post.assert_called_once_with(
        "https://api.pushbullet.com/v2/pushes",
        headers={"Access-Token": "fake-token", "Content-Type": "application/json"},
        json={"type": "note", "title": "Trade Bot Sim - Daily Report", "body": "report body text"},
        timeout=10,
    )


@patch("src.notifier.pushbullet_notifier.requests.post")
def test_send_report_raises_notifier_error_on_failure(mock_post):
    mock_post.return_value = make_response(status_ok=False)

    notifier = PushbulletNotifier("fake-token")
    with pytest.raises(NotifierError):
        notifier.send_report("Title", "Body")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/notifier/test_pushbullet_notifier.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.notifier.pushbullet_notifier'`

- [ ] **Step 3: Write `src/notifier/pushbullet_notifier.py`**

```python
import requests

PUSHBULLET_API_URL = "https://api.pushbullet.com/v2/pushes"


class NotifierError(Exception):
    pass


class PushbulletNotifier:
    def __init__(self, access_token: str):
        self.access_token = access_token

    def send_report(self, title: str, body: str) -> None:
        try:
            response = requests.post(
                PUSHBULLET_API_URL,
                headers={"Access-Token": self.access_token, "Content-Type": "application/json"},
                json={"type": "note", "title": title, "body": body},
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise NotifierError(f"Failed to send Pushbullet notification: {exc}") from exc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/notifier/test_pushbullet_notifier.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Remove `pushbullet.py` from `requirements.txt`**

Edit `requirements.txt` to delete the `pushbullet.py==0.12.0` line (added in Task 1, no longer needed).

- [ ] **Step 6: Commit**

```bash
git add src/notifier tests/notifier requirements.txt
git commit -m "feat: add Pushbullet notifier via direct REST API"
```

---

### Task 15: Scheduler Wiring

**Files:**
- Create: `src/scheduler/jobs.py`
- Test: `tests/scheduler/test_jobs.py`
- Create: `tests/scheduler/__init__.py` (empty)

**Interfaces:**
- Produces: `build_scheduler(hourly_tick_fn, daily_report_fn) -> BlockingScheduler` — configures one job firing at the top of every hour (`Europe/Istanbul`) and one job firing daily at 00:00 (`Europe/Istanbul`)

- [ ] **Step 1: Write the failing tests**

`tests/scheduler/test_jobs.py`:

```python
from src.scheduler.jobs import build_scheduler


def noop():
    pass


def test_build_scheduler_registers_two_jobs():
    scheduler = build_scheduler(noop, noop)
    jobs = scheduler.get_jobs()
    assert len(jobs) == 2


def test_scheduler_uses_istanbul_timezone():
    scheduler = build_scheduler(noop, noop)
    assert str(scheduler.timezone) == "Europe/Istanbul"


def test_daily_job_trigger_fires_at_midnight():
    scheduler = build_scheduler(noop, noop)
    daily_job = next(j for j in scheduler.get_jobs() if j.func is noop and "hour='0'" in str(j.trigger))
    assert "minute='0'" in str(daily_job.trigger)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/scheduler/test_jobs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.scheduler.jobs'`

- [ ] **Step 3: Write `src/scheduler/jobs.py`**

```python
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger


def build_scheduler(hourly_tick_fn, daily_report_fn) -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone="Europe/Istanbul")
    scheduler.add_job(hourly_tick_fn, CronTrigger(minute=0))
    scheduler.add_job(daily_report_fn, CronTrigger(hour=0, minute=0))
    return scheduler
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/scheduler/test_jobs.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/scheduler tests/scheduler
git commit -m "feat: add APScheduler wiring for hourly ticks and daily report"
```

---

### Task 16: Main Application Wiring

**Files:**
- Create: `main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: everything from Tasks 1-15
- Produces: `build_agents(conn, config) -> list[Agent]`; `make_hourly_tick(engine, config) -> Callable[[], None]`; `make_daily_report(conn, market_data, agents, notifier, config) -> Callable[[], None]`; `main() -> None` (only invoked under `if __name__ == "__main__"`, never at import time, so the module can be imported safely in tests)

- [ ] **Step 1: Write the failing tests**

`tests/test_main.py`:

```python
from unittest.mock import MagicMock

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


def test_hourly_tick_calls_engine_run_tick():
    fake_engine = MagicMock()
    config = Config()

    hourly_tick = main.make_hourly_tick(fake_engine, config)
    hourly_tick()

    fake_engine.run_tick.assert_called_once_with(config.WATCHLIST)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_main.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 3: Write `main.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_main.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the full test suite**

Run: `pytest -v`
Expected: All tests across every module PASS

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: wire application entrypoint with scheduler and 5 agents"
```

---

### Task 17: Deployment (Oracle Cloud Free Tier)

**Files:**
- Create: `deploy/trade-bot-sim.service`
- Create: `deploy/setup_vm.sh`
- Create: `deploy/README.md`

**Interfaces:**
- Consumes: `requirements.txt`, `main.py`, `.env.example` (Task 1, Task 16)
- Produces: a systemd unit and a setup script that install and run the application as the `tradebot` system user under `/opt/trade-bot-sim`

- [ ] **Step 1: Write `deploy/trade-bot-sim.service`**

```ini
[Unit]
Description=Trade Bot Sim - crypto paper trading simulation
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/trade-bot-sim
EnvironmentFile=/opt/trade-bot-sim/.env
ExecStart=/opt/trade-bot-sim/venv/bin/python /opt/trade-bot-sim/main.py
Restart=always
RestartSec=10
User=tradebot

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Write `deploy/setup_vm.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/opt/trade-bot-sim

sudo useradd --system --create-home --shell /usr/sbin/nologin tradebot || true
sudo mkdir -p "$APP_DIR"

sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip rsync

sudo rsync -a --exclude venv --exclude .git --exclude "*.db" ./ "$APP_DIR"/

cd "$APP_DIR"
sudo python3 -m venv venv
sudo ./venv/bin/pip install -r requirements.txt

if [ ! -f "$APP_DIR/.env" ]; then
  sudo cp .env.example "$APP_DIR/.env"
  echo "Created $APP_DIR/.env from template - edit it and set PUSHBULLET_TOKEN before starting."
fi

sudo cp deploy/trade-bot-sim.service /etc/systemd/system/trade-bot-sim.service
sudo chown -R tradebot:tradebot "$APP_DIR"

sudo systemctl daemon-reload
sudo systemctl enable trade-bot-sim

echo "Setup complete."
echo "1. Edit $APP_DIR/.env and set PUSHBULLET_TOKEN"
echo "2. Start with: sudo systemctl start trade-bot-sim"
echo "3. Check status with: sudo systemctl status trade-bot-sim"
echo "4. Tail logs with: sudo journalctl -u trade-bot-sim -f"
```

- [ ] **Step 3: Make the setup script executable**

Run: `chmod +x deploy/setup_vm.sh`

- [ ] **Step 4: Write `deploy/README.md`**

```markdown
# Deployment - Oracle Cloud Free Tier

## Prerequisites

- An Oracle Cloud Free Tier "Always Free" VM instance (Ubuntu), reachable via SSH
- A Pushbullet account with an access token (Settings -> Account -> Create Access Token)

## Steps

1. Copy this repository to the VM (e.g. `git clone` or `scp -r`).
2. SSH into the VM and run:

   ```bash
   cd trade-bot-sim
   ./deploy/setup_vm.sh
   ```

3. Edit `/opt/trade-bot-sim/.env` and set `PUSHBULLET_TOKEN` to your real token.
4. Start the service:

   ```bash
   sudo systemctl start trade-bot-sim
   ```

5. Verify it's running:

   ```bash
   sudo systemctl status trade-bot-sim
   sudo journalctl -u trade-bot-sim -f
   ```

## What to expect

- The bot polls Binance and evaluates all 5 agents once per hour.
- Every day at 00:00 Europe/Istanbul time, a summary is pushed to your Pushbullet-connected devices.
- If the VM reboots or the process crashes, systemd (`Restart=always`) brings it back up automatically; portfolio state is restored from `/opt/trade-bot-sim/trade_bot_sim.db`.

## Updating the deployed code

```bash
cd trade-bot-sim
git pull
sudo rsync -a --exclude venv --exclude .git --exclude "*.db" ./ /opt/trade-bot-sim/
sudo systemctl restart trade-bot-sim
```
```

- [ ] **Step 5: Commit**

```bash
git add deploy
git commit -m "docs: add Oracle Cloud Free Tier deployment scripts and instructions"
```

---

## Self-Review Notes

- **Spec coverage:** Task 1-4 cover data/config foundations; Tasks 5-11 cover all 5 strategies plus shared indicators (spec section 4); Task 12 covers the engine, shared risk rules, and per-agent isolation (spec sections 3 and 5); Task 13-14 cover reporting and Pushbullet delivery (spec section 6); Task 15-16 wire scheduling and the entrypoint (spec sections 3 and 6); Task 17 covers Oracle Cloud deployment (spec section 8). Testing approach (spec section 7) is satisfied per-task with `pytest`, and no task performs live network calls in its automated tests.
- **Type consistency verified:** `Signal`/`Action` from Task 5 are used identically across Tasks 7-12; `Portfolio.to_state()`/`from_state()` (Task 2) match the dict shape consumed by `save_portfolio_state`/`load_portfolio_state` (Task 3) and produced/consumed again in Task 16's `build_agents`; `get_trades_since` (Task 3) return shape matches what `compute_agent_report` (Task 13) and the engine's stop-loss/report tests expect; `SimulationEngine`/`Agent` constructor signatures in Task 12 match their usage in Task 16.
- **No placeholders:** every step contains runnable code and exact commands; no task references a type or function not defined earlier in the plan.
