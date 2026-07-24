# Local Live Minute-Cadence Trading Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Botlar dakikada bir 1m mumlara bakıp karar versin; kullanıcı hangi botun hangi kararı verdiğini ve net kâr/zararını `localhost:8000`'de canlı izlesin.

**Architecture:** `SimulationEngine`'e thread-safe bir `LiveState` enjekte edilir; her tick sonunda her botun son kararı ve net K/Z'si buraya yazılır. `BlockingScheduler` ana thread'de her dakika `run_tick` çalıştırır; Flask paneli ayrı bir daemon thread'de `LiveState`'i JSON olarak sunar ve tek sayfalık HTML her 5 sn'de yeniler.

**Tech Stack:** Python 3.11+, APScheduler, Flask, SQLite, pytest.

## Global Constraints

- Motor `live_state=None` ile geriye uyumlu kalmalı — mevcut testler kırılmamalı.
- HOLD kararları DB'ye yazılmaz; sadece BUY/SELL `trades` tablosuna yazılır (mevcut davranış).
- Tek-worker `ThreadPoolExecutor(max_workers=1)` korunur.
- Net K/Z, tick'te zaten çekilmiş fiyatlarla hesaplanır — ekstra API çağrısı eklenmez.
- Strateji mantığına, portföy/işlem hesaplarına, DB şemasına dokunulmaz.
- Testler `pytest` ile çalışır; komutlar proje kökünden verilir.

---

### Task 1: Config'e kline aralığı ve web portu ekle

**Files:**
- Modify: `src/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config.KLINE_INTERVAL: str` (`"1m"`), `Config.WEB_PORT: int` (`8000`).

- [ ] **Step 1: Testi yaz (fail)**

`tests/test_config.py` içine ekle:

```python
def test_config_has_kline_interval_and_web_port():
    from src.config import Config

    config = Config()
    assert config.KLINE_INTERVAL == "1m"
    assert config.WEB_PORT == 8000
```

- [ ] **Step 2: Testi çalıştır, fail gör**

Run: `python -m pytest tests/test_config.py::test_config_has_kline_interval_and_web_port -v`
Expected: FAIL (AttributeError: 'Config' object has no attribute 'KLINE_INTERVAL')

- [ ] **Step 3: Config'i güncelle**

`src/config.py` içinde `__init__` gövdesine ekle (mevcut satırların yanına):

```python
        self.KLINE_INTERVAL = os.getenv("KLINE_INTERVAL", "1m")
        self.WEB_PORT = int(os.getenv("WEB_PORT", "8000"))
```

- [ ] **Step 4: Testi çalıştır, geç gör**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: add KLINE_INTERVAL and WEB_PORT config"
```

---

### Task 2: Thread-safe LiveState

**Files:**
- Create: `src/web/__init__.py`
- Create: `src/web/live_state.py`
- Test: `tests/web/__init__.py`, `tests/web/test_live_state.py`

**Interfaces:**
- Produces:
  - `class LiveState` with:
    - `update_agent(name: str, decision: str, symbol: str | None, pnl_abs: float, pnl_pct: float, cash: float, total_value: float, positions: dict) -> None`
    - `snapshot() -> dict` returning `{"updated_at": str | None, "total_value": float, "total_pnl_abs": float, "agents": list[dict]}` where each agent dict has keys `name, decision, symbol, pnl_abs, pnl_pct, cash, total_value, positions, updated_at`.
  - `snapshot()` aggregates: `total_value` = sum of agent `total_value`; `total_pnl_abs` = sum of agent `pnl_abs`; `updated_at` = en son güncelleme zaman damgası (yoksa `None`). Agent listesi eklenme sırasına göre.

- [ ] **Step 1: Test paketini oluştur**

`tests/web/__init__.py` — boş dosya.

- [ ] **Step 2: Testi yaz (fail)**

`tests/web/test_live_state.py`:

```python
from src.web.live_state import LiveState


def test_empty_snapshot():
    state = LiveState()
    snap = state.snapshot()
    assert snap["updated_at"] is None
    assert snap["agents"] == []
    assert snap["total_value"] == 0.0
    assert snap["total_pnl_abs"] == 0.0


def test_update_and_snapshot():
    state = LiveState()
    state.update_agent(
        name="trend_follower",
        decision="BUY",
        symbol="BTCUSDT",
        pnl_abs=142.30,
        pnl_pct=1.42,
        cash=5000.0,
        total_value=10142.30,
        positions={"BTCUSDT": {"quantity": 0.1, "avg_entry_price": 50000.0}},
    )
    snap = state.snapshot()
    assert snap["updated_at"] is not None
    assert len(snap["agents"]) == 1
    agent = snap["agents"][0]
    assert agent["name"] == "trend_follower"
    assert agent["decision"] == "BUY"
    assert agent["symbol"] == "BTCUSDT"
    assert agent["pnl_abs"] == 142.30
    assert snap["total_value"] == 10142.30
    assert snap["total_pnl_abs"] == 142.30


def test_update_overwrites_same_agent():
    state = LiveState()
    state.update_agent("a", "HOLD", None, 0.0, 0.0, 10000.0, 10000.0, {})
    state.update_agent("a", "SELL", "ETHUSDT", -5.0, -0.05, 10005.0, 9995.0, {})
    snap = state.snapshot()
    assert len(snap["agents"]) == 1
    assert snap["agents"][0]["decision"] == "SELL"
    assert snap["total_pnl_abs"] == -5.0


def test_aggregates_multiple_agents():
    state = LiveState()
    state.update_agent("a", "HOLD", None, 10.0, 0.1, 5000.0, 10010.0, {})
    state.update_agent("b", "BUY", "BTCUSDT", -3.0, -0.03, 4000.0, 9997.0, {})
    snap = state.snapshot()
    assert [a["name"] for a in snap["agents"]] == ["a", "b"]
    assert snap["total_value"] == 20007.0
    assert round(snap["total_pnl_abs"], 6) == 7.0
```

- [ ] **Step 3: Testi çalıştır, fail gör**

Run: `python -m pytest tests/web/test_live_state.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'src.web')

- [ ] **Step 4: Paketi ve LiveState'i yaz**

`src/web/__init__.py` — boş dosya.

`src/web/live_state.py`:

```python
import datetime
import threading


class LiveState:
    """Thread-safe canlı bot durumu. Motor yazar, web sunucusu okur."""

    def __init__(self):
        self._lock = threading.Lock()
        self._agents: dict[str, dict] = {}
        self._updated_at: str | None = None

    def update_agent(
        self,
        name: str,
        decision: str,
        symbol: str | None,
        pnl_abs: float,
        pnl_pct: float,
        cash: float,
        total_value: float,
        positions: dict,
    ) -> None:
        now = datetime.datetime.now(datetime.UTC).isoformat()
        with self._lock:
            self._agents[name] = {
                "name": name,
                "decision": decision,
                "symbol": symbol,
                "pnl_abs": pnl_abs,
                "pnl_pct": pnl_pct,
                "cash": cash,
                "total_value": total_value,
                "positions": positions,
                "updated_at": now,
            }
            self._updated_at = now

    def snapshot(self) -> dict:
        with self._lock:
            agents = [dict(a) for a in self._agents.values()]
            total_value = sum(a["total_value"] for a in agents)
            total_pnl_abs = sum(a["pnl_abs"] for a in agents)
            return {
                "updated_at": self._updated_at,
                "total_value": total_value,
                "total_pnl_abs": total_pnl_abs,
                "agents": agents,
            }
```

- [ ] **Step 5: Testleri çalıştır, geç gör**

Run: `python -m pytest tests/web/test_live_state.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add src/web/__init__.py src/web/live_state.py tests/web/__init__.py tests/web/test_live_state.py
git commit -m "feat: add thread-safe LiveState for live dashboard"
```

---

### Task 3: Motoru LiveState ile besle + 1m kline aralığı

**Files:**
- Modify: `src/engine/simulation_engine.py`
- Modify: `main.py:47-51` (`make_hourly_tick`) — kline interval'ı geçir
- Test: `tests/engine/test_simulation_engine.py`

**Interfaces:**
- Consumes: `LiveState.update_agent(...)` (Task 2), `Config.KLINE_INTERVAL` (Task 1).
- Produces: `SimulationEngine.__init__(self, agents, market_data_client, storage_conn, live_state=None)`; `run_tick(self, watchlist, interval="1h")`.

**Notes:** Karar önceliği — bir botun tick'inde birden çok sembolde işlem olabilir; canlı panelde tek "son karar" gösterilir. Kural: tick sırasında gerçekleşen **son** BUY/SELL işlemi (varsa) `decision`/`symbol` olur; hiç işlem yoksa `decision="HOLD"`, `symbol=None`. Net K/Z tick'in `prices_by_symbol`'ü ile `portfolio.total_pnl` üzerinden hesaplanır.

- [ ] **Step 1: Testi yaz (fail)**

`tests/engine/test_simulation_engine.py` içine ekle (mevcut import'lara `from src.web.live_state import LiveState` ekle; dosyadaki mevcut fake/mock yardımcılarını kullan):

```python
def test_run_tick_records_hold_decision_in_live_state(monkeypatch):
    # Strateji hep HOLD döndürsün
    from src.strategies.base import Action, Signal

    class HoldStrategy:
        def generate_signal(self, symbol, candles):
            return Signal(action=Action.HOLD, symbol=symbol)

    from src.engine.simulation_engine import Agent, SimulationEngine
    from src.portfolio.portfolio import Portfolio

    conn = _make_conn()  # dosyadaki mevcut yardımcı; yoksa init_db(":memory:")
    market = _FakeMarket(price=100.0)  # dosyadaki mevcut fake; get_klines close=100 döndürür
    agent = Agent("holder", HoldStrategy(), Portfolio(10_000.0))
    live = LiveState()
    engine = SimulationEngine([agent], market, conn, live_state=live)

    engine.run_tick(["BTCUSDT"])

    snap = live.snapshot()
    assert len(snap["agents"]) == 1
    a = snap["agents"][0]
    assert a["name"] == "holder"
    assert a["decision"] == "HOLD"
    assert a["symbol"] is None
    assert a["total_value"] == 10_000.0


def test_run_tick_records_buy_decision_in_live_state():
    from src.strategies.base import Action, Signal

    class BuyStrategy:
        def generate_signal(self, symbol, candles):
            return Signal(action=Action.BUY, symbol=symbol)

    from src.engine.simulation_engine import Agent, SimulationEngine
    from src.portfolio.portfolio import Portfolio

    conn = _make_conn()
    market = _FakeMarket(price=100.0)
    agent = Agent("buyer", BuyStrategy(), Portfolio(10_000.0))
    live = LiveState()
    engine = SimulationEngine([agent], market, conn, live_state=live)

    engine.run_tick(["BTCUSDT"])

    a = live.snapshot()["agents"][0]
    assert a["decision"] == "BUY"
    assert a["symbol"] == "BTCUSDT"


def test_run_tick_without_live_state_still_works():
    from src.strategies.base import Action, Signal

    class HoldStrategy:
        def generate_signal(self, symbol, candles):
            return Signal(action=Action.HOLD, symbol=symbol)

    from src.engine.simulation_engine import Agent, SimulationEngine
    from src.portfolio.portfolio import Portfolio

    conn = _make_conn()
    market = _FakeMarket(price=100.0)
    agent = Agent("holder", HoldStrategy(), Portfolio(10_000.0))
    engine = SimulationEngine([agent], market, conn)  # live_state yok

    engine.run_tick(["BTCUSDT"])  # exception atmamalı


def test_run_tick_passes_interval_to_market():
    from src.strategies.base import Action, Signal

    class HoldStrategy:
        def generate_signal(self, symbol, candles):
            return Signal(action=Action.HOLD, symbol=symbol)

    from src.engine.simulation_engine import Agent, SimulationEngine
    from src.portfolio.portfolio import Portfolio

    seen = {}

    class RecordingMarket(_FakeMarket):
        def get_klines(self, symbol, interval="1h"):
            seen["interval"] = interval
            return super().get_klines(symbol)

    conn = _make_conn()
    agent = Agent("holder", HoldStrategy(), Portfolio(10_000.0))
    engine = SimulationEngine([agent], RecordingMarket(price=100.0), conn)

    engine.run_tick(["BTCUSDT"], interval="1m")
    assert seen["interval"] == "1m"
```

Not: `_make_conn` / `_FakeMarket` isimleri dosyadaki mevcut yardımcılara göre uyarlanır. Dosyada bu yardımcılar yoksa: `conn = init_db(":memory:")` ve `_FakeMarket`, `get_klines(symbol, interval="1h")` ile `[{"open_time":0,"open":price,"high":price,"low":price,"close":price,"volume":1.0}]` döndüren, `get_current_price` = `price` olan küçük bir sınıf olarak eklenir.

- [ ] **Step 2: Testi çalıştır, fail gör**

Run: `python -m pytest tests/engine/test_simulation_engine.py -v`
Expected: FAIL (SimulationEngine `live_state`/`interval` kabul etmiyor)

- [ ] **Step 3: Motoru güncelle**

`src/engine/simulation_engine.py`:

`__init__` imzasını değiştir:

```python
    def __init__(self, agents: list[Agent], market_data_client, storage_conn, live_state=None):
        self.agents = agents
        self.market_data = market_data_client
        self.storage = storage_conn
        self.live_state = live_state
```

`run_tick`'i değiştir (interval parametresi + fiyatları alt fonksiyona geçir):

```python
    def run_tick(self, watchlist: list[str], interval: str = "1h") -> None:
        candles_by_symbol = {symbol: self.market_data.get_klines(symbol, interval=interval) for symbol in watchlist}
        prices_by_symbol = {symbol: candles_by_symbol[symbol][-1]["close"] for symbol in watchlist}

        for agent in self.agents:
            try:
                self._run_agent_tick(agent, watchlist, candles_by_symbol, prices_by_symbol)
            except Exception:
                logger.exception("Agent %s failed this tick", agent.name)
```

`_run_agent_tick`'te karar takibi ve LiveState güncellemesi ekle:

```python
    def _run_agent_tick(self, agent, watchlist, candles_by_symbol, prices_by_symbol) -> None:
        decision = "HOLD"
        decision_symbol = None
        try:
            self._apply_stop_losses(agent, prices_by_symbol)
            for symbol in watchlist:
                signal = agent.strategy.generate_signal(symbol, candles_by_symbol[symbol])
                price = prices_by_symbol[symbol]
                if signal.action == Action.BUY:
                    if self._execute_buy(agent, symbol, price, prices_by_symbol):
                        decision, decision_symbol = "BUY", symbol
                elif signal.action == Action.SELL:
                    if self._execute_sell(agent, symbol, price):
                        decision, decision_symbol = "SELL", symbol
        finally:
            state = agent.portfolio.to_state()
            save_portfolio_state(self.storage, agent.name, state["cash"], state["positions"])
            self._update_live_state(agent, decision, decision_symbol, prices_by_symbol)
```

`_execute_buy` / `_execute_sell`, işlem gerçekleşince `True`, aksi halde `False` döndürsün:

```python
    def _execute_buy(self, agent: Agent, symbol: str, price: float, prices_by_symbol: dict[str, float]) -> bool:
        portfolio_value = agent.portfolio.total_value(prices_by_symbol)
        max_position_value = portfolio_value * POSITION_SIZE_PCT

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

    def _execute_sell(self, agent: Agent, symbol: str, price: float) -> bool:
        if symbol not in agent.portfolio.positions:
            return False
        quantity = agent.portfolio.positions[symbol].quantity
        agent.portfolio.sell(symbol, price, quantity)
        self._log_trade(agent, symbol)
        return True
```

Yeni yardımcı metot ekle (sınıfın sonuna):

```python
    def _update_live_state(self, agent, decision, decision_symbol, prices_by_symbol) -> None:
        if self.live_state is None:
            return
        pnl_abs, pnl_pct = agent.portfolio.total_pnl(prices_by_symbol)
        total_value = agent.portfolio.total_value(prices_by_symbol)
        positions = {
            symbol: {"quantity": pos.quantity, "avg_entry_price": pos.avg_entry_price}
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
        )
```

Not: `_apply_stop_losses` içindeki `self._execute_sell(...)` çağrısı artık `bool` döndürür; dönüş değeri orada kullanılmıyor, olduğu gibi bırak (stop-loss satışı da bir karar sayılmaz, in-loop kararların üzerine yazılmaz — stop-loss döngüden önce çalışır).

- [ ] **Step 4: Testleri çalıştır, geç gör**

Run: `python -m pytest tests/engine/test_simulation_engine.py -v`
Expected: PASS (yeni testler + mevcut testler)

- [ ] **Step 5: Commit**

```bash
git add src/engine/simulation_engine.py tests/engine/test_simulation_engine.py
git commit -m "feat: feed LiveState from engine and pass kline interval"
```

---

### Task 4: Scheduler dakikalık interval

**Files:**
- Modify: `src/scheduler/jobs.py`
- Test: `tests/scheduler/test_jobs.py`

**Interfaces:**
- Produces: `build_scheduler(minute_tick_fn, daily_report_fn)` — tick job `IntervalTrigger(minutes=1)`, rapor job `CronTrigger(hour=0, minute=0)`.

- [ ] **Step 1: Testi yaz (fail)**

`tests/scheduler/test_jobs.py` içine ekle (mevcut testleri okuyup üslubu izle):

```python
def test_scheduler_uses_minute_interval_trigger():
    from apscheduler.triggers.interval import IntervalTrigger

    from src.scheduler.jobs import build_scheduler

    scheduler = build_scheduler(lambda: None, lambda: None)
    tick_job = scheduler.get_jobs()[0]
    assert isinstance(tick_job.trigger, IntervalTrigger)
    assert tick_job.trigger.interval.total_seconds() == 60
```

Mevcut testlerden biri `CronTrigger(minute=0)` bekliyorsa onu `IntervalTrigger` beklentisine göre güncelle (davranış bilerek değişiyor).

- [ ] **Step 2: Testi çalıştır, fail gör**

Run: `python -m pytest tests/scheduler/test_jobs.py -v`
Expected: FAIL (tick job hâlâ CronTrigger)

- [ ] **Step 3: Scheduler'ı güncelle**

`src/scheduler/jobs.py`:

```python
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger


def build_scheduler(minute_tick_fn, daily_report_fn) -> BlockingScheduler:
    # Tek-worker executor: 00:00'da hem dakikalık tick hem günlük rapor tetiklenir;
    # paylaşılan SQLite bağlantısı ve portföy state'i için işleri seri çalıştırırız.
    scheduler = BlockingScheduler(
        timezone="Europe/Istanbul",
        executors={"default": ThreadPoolExecutor(max_workers=1)},
    )
    scheduler.add_job(minute_tick_fn, IntervalTrigger(minutes=1))
    scheduler.add_job(daily_report_fn, CronTrigger(hour=0, minute=0))
    return scheduler
```

- [ ] **Step 4: Testleri çalıştır, geç gör**

Run: `python -m pytest tests/scheduler/test_jobs.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/scheduler/jobs.py tests/scheduler/test_jobs.py
git commit -m "feat: run tick every minute via IntervalTrigger"
```

---

### Task 5: Flask dashboard uygulaması

**Files:**
- Create: `src/web/dashboard.py`
- Modify: `requirements.txt`
- Test: `tests/web/test_dashboard.py`

**Interfaces:**
- Consumes: `LiveState.snapshot()` (Task 2).
- Produces:
  - `create_app(live_state) -> flask.Flask` — `GET /` HTML döner (200, `text/html`), `GET /api/state` `live_state.snapshot()`'ı JSON olarak döner.
  - `run_dashboard(live_state, port: int) -> None` — Flask'i verilen portta çalıştırır (bloklar; çağıran daemon thread'de çağırır).

- [ ] **Step 1: requirements'a flask ekle**

`requirements.txt` sonuna ekle:

```
Flask==3.0.3
```

Kur: `python -m pip install Flask==3.0.3`

- [ ] **Step 2: Testi yaz (fail)**

`tests/web/test_dashboard.py`:

```python
from src.web.dashboard import create_app
from src.web.live_state import LiveState


def _client():
    state = LiveState()
    state.update_agent("trend_follower", "BUY", "BTCUSDT", 142.3, 1.42, 5000.0, 10142.3, {})
    app = create_app(state)
    app.config.update(TESTING=True)
    return app.test_client()


def test_api_state_returns_snapshot_json():
    client = _client()
    resp = client.get("/api/state")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total_value"] == 10142.3
    assert len(data["agents"]) == 1
    assert data["agents"][0]["decision"] == "BUY"


def test_index_returns_html():
    client = _client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.content_type
    assert b"/api/state" in resp.data  # sayfa JSON endpoint'ini poll ediyor
```

- [ ] **Step 3: Testi çalıştır, fail gör**

Run: `python -m pytest tests/web/test_dashboard.py -v`
Expected: FAIL (ModuleNotFoundError: src.web.dashboard)

- [ ] **Step 4: Dashboard'u yaz**

`src/web/dashboard.py`:

```python
from flask import Flask, Response, jsonify

INDEX_HTML = """<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<title>Trade Bot Sim - Canlı Panel</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 24px; background: #0f1115; color: #e6e6e6; }
  h1 { font-size: 20px; }
  .totals { margin: 12px 0 20px; font-size: 16px; }
  table { border-collapse: collapse; width: 100%; }
  th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #2a2d34; }
  th { color: #9aa0aa; font-weight: 600; }
  .BUY { color: #2ecc71; font-weight: 700; }
  .SELL { color: #e74c3c; font-weight: 700; }
  .HOLD { color: #8a8f98; font-weight: 700; }
  .pos { color: #2ecc71; }
  .neg { color: #e74c3c; }
  .muted { color: #8a8f98; font-size: 12px; }
</style>
</head>
<body>
<h1>Trade Bot Sim — Canlı Panel</h1>
<div class="totals" id="totals">Yükleniyor…</div>
<table>
  <thead>
    <tr><th>Bot</th><th>Karar</th><th>Sembol</th><th>Net K/Z ($)</th><th>Net K/Z (%)</th><th>Nakit</th><th>Portföy</th></tr>
  </thead>
  <tbody id="rows"></tbody>
</table>
<p class="muted" id="updated"></p>
<script>
function fmt(n) { return (n >= 0 ? "+" : "") + n.toFixed(2); }
function cls(n) { return n >= 0 ? "pos" : "neg"; }
async function refresh() {
  try {
    const r = await fetch("/api/state");
    const d = await r.json();
    document.getElementById("totals").innerHTML =
      "Toplam portföy: <b>$" + d.total_value.toFixed(2) + "</b> &nbsp; " +
      "Toplam net K/Z: <b class='" + cls(d.total_pnl_abs) + "'>$" + fmt(d.total_pnl_abs) + "</b>";
    const rows = d.agents.map(a =>
      "<tr>" +
      "<td>" + a.name + "</td>" +
      "<td class='" + a.decision + "'>" + a.decision + "</td>" +
      "<td>" + (a.symbol || "—") + "</td>" +
      "<td class='" + cls(a.pnl_abs) + "'>$" + fmt(a.pnl_abs) + "</td>" +
      "<td class='" + cls(a.pnl_pct) + "'>" + fmt(a.pnl_pct) + "%</td>" +
      "<td>$" + a.cash.toFixed(2) + "</td>" +
      "<td>$" + a.total_value.toFixed(2) + "</td>" +
      "</tr>"
    ).join("");
    document.getElementById("rows").innerHTML = rows;
    document.getElementById("updated").textContent =
      d.updated_at ? ("Son güncelleme: " + d.updated_at) : "Henüz veri yok";
  } catch (e) {
    document.getElementById("updated").textContent = "Bağlantı hatası, yeniden denenecek…";
  }
}
refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>
"""


def create_app(live_state) -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index() -> Response:
        return Response(INDEX_HTML, mimetype="text/html")

    @app.get("/api/state")
    def api_state():
        return jsonify(live_state.snapshot())

    return app


def run_dashboard(live_state, port: int) -> None:
    app = create_app(live_state)
    app.run(host="127.0.0.1", port=port, threaded=True, use_reloader=False)
```

- [ ] **Step 5: Testleri çalıştır, geç gör**

Run: `python -m pytest tests/web/test_dashboard.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add src/web/dashboard.py tests/web/test_dashboard.py requirements.txt
git commit -m "feat: add Flask live dashboard"
```

---

### Task 6: main.py'yi bağla — LiveState + web thread + dakikalık tick

**Files:**
- Modify: `main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: `LiveState` (Task 2), `run_dashboard` (Task 5), `SimulationEngine(..., live_state=...)` ve `run_tick(watchlist, interval=...)` (Task 3), `build_scheduler` (Task 4), `Config.KLINE_INTERVAL`/`WEB_PORT` (Task 1).
- Produces: `make_minute_tick(engine, config)` — her çağrıda `engine.run_tick(config.WATCHLIST, interval=config.KLINE_INTERVAL)` çalıştıran fonksiyon döner.

- [ ] **Step 1: Testi yaz (fail)**

`tests/test_main.py` içine ekle (mevcut testlerin stil/mock yaklaşımını izle):

```python
def test_make_minute_tick_calls_run_tick_with_interval():
    from unittest.mock import MagicMock

    from main import make_minute_tick

    engine = MagicMock()
    config = MagicMock()
    config.WATCHLIST = ["BTCUSDT"]
    config.KLINE_INTERVAL = "1m"

    tick = make_minute_tick(engine, config)
    tick()

    engine.run_tick.assert_called_once_with(["BTCUSDT"], interval="1m")
```

Not: `main.py`'de `make_hourly_tick` varsa ve başka test ona bağlıysa, o testi `make_minute_tick`'e göre güncelle (fonksiyon yeniden adlandırılıyor).

- [ ] **Step 2: Testi çalıştır, fail gör**

Run: `python -m pytest tests/test_main.py -v`
Expected: FAIL (ImportError: cannot import name 'make_minute_tick')

- [ ] **Step 3: main.py'yi güncelle**

`src/web` import'larını ekle:

```python
import threading

from src.web.dashboard import run_dashboard
from src.web.live_state import LiveState
```

`make_hourly_tick`'i şununla değiştir:

```python
def make_minute_tick(engine: SimulationEngine, config: Config):
    def minute_tick() -> None:
        engine.run_tick(config.WATCHLIST, interval=config.KLINE_INTERVAL)

    return minute_tick
```

`main()` gövdesini güncelle (agents/engine oluşturmayı LiveState ile bağla, web thread'ini başlat, dakikalık tick kullan):

```python
def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    config = Config()
    conn = init_db(config.DB_PATH)
    market_data = MarketDataClient()
    notifier = PushbulletNotifier(config.PUSHBULLET_TOKEN)

    live_state = LiveState()
    agents = build_agents(conn, config)
    engine = SimulationEngine(agents, market_data, conn, live_state=live_state)

    minute_tick = make_minute_tick(engine, config)
    daily_report = make_daily_report(conn, market_data, agents, notifier, config)

    web_thread = threading.Thread(
        target=run_dashboard, args=(live_state, config.WEB_PORT), daemon=True
    )
    web_thread.start()
    logging.info("Canlı panel: http://127.0.0.1:%d", config.WEB_PORT)

    scheduler = build_scheduler(minute_tick, daily_report)
    scheduler.start()
```

- [ ] **Step 4: Testleri çalıştır, geç gör**

Run: `python -m pytest tests/test_main.py -v`
Expected: PASS

- [ ] **Step 5: Tüm testleri çalıştır**

Run: `python -m pytest -q`
Expected: PASS (tüm suite yeşil)

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: wire LiveState, web dashboard, and minute tick into main"
```

---

### Task 7: Elle doğrulama (opsiyonel ama önerilir)

**Files:** yok (manuel çalıştırma).

- [ ] **Step 1: Uygulamayı çalıştır**

Run: `python main.py`
Expected: Log'da "Canlı panel: http://127.0.0.1:8000" görünür; scheduler her dakika tick loglar.

- [ ] **Step 2: Paneli aç**

Tarayıcıda `http://127.0.0.1:8000` aç. Bir dakika içinde 5 botun satırı, kararları (BUY/SELL/HOLD) ve net K/Z'leri görünür; sayfa 5 sn'de bir yenilenir.

- [ ] **Step 3: Ctrl+C ile durdur**

Expected: Uygulama temiz kapanır (daemon web thread ana thread ile birlikte sonlanır).

---

## Self-Review Notu

- Spec kapsamı: dakikalık tick (Task 1,3,4,6) ✅; HOLD dahil karar yakalama (Task 2,3) ✅;
  web paneli + net K/Z (Task 2,5,6) ✅; geriye uyumluluk (Task 3 `live_state=None` testi) ✅;
  günlük rapor/Pushbullet dokunulmadı (Task 6 korundu) ✅.
- Tip tutarlılığı: `LiveState.update_agent`/`snapshot` alan adları Task 2 → Task 3/5/6 boyunca
  aynı (`decision, symbol, pnl_abs, pnl_pct, cash, total_value, positions, updated_at`).
- `run_tick(watchlist, interval)` ve `SimulationEngine(..., live_state=None)` imzaları Task 3'te
  tanımlanıp Task 6'da tutarlı kullanılıyor.
