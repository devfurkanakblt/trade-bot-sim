# Crypto Paper-Trading Simulation — Design Spec

## 1. Purpose

Build a 24/7 paper-trading simulation running 5 independent Python trading agents against **live, real cryptocurrency market data**. No real money or real orders are involved — every agent starts with a virtual $10,000 balance and trades are simulated fills against real-time prices. The goal is to answer: "if these bots' decisions had been executed for real, what would the profit/loss look like?"

Once a day, at **00:00 Europe/Istanbul time**, the system pushes a clean, readable performance report to the user via Pushbullet, and stores the report history for later review.

## 2. Scope Decisions

These were explicitly delegated to the assistant by the user and are now fixed:

- **Asset class:** Cryptocurrency only (not forex/stocks/metals). Rationale: crypto markets trade 24/7 with no close, which matches the "always running" requirement naturally, and reliable free market data is available with no account/KYC required.
- **Data source:** Binance public REST API (`/api/v3/klines`, `/api/v3/ticker/price`) — free, unauthenticated, no API key required for market data.
- **Watchlist:** `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT` — a small basket of liquid pairs, shared by all 5 agents.
- **Signal timeframe:** 1-hour candles. Reduces noise vs. shorter timeframes and keeps API call volume well within free rate limits.
- **Capital model:** Each of the 5 agents gets its own independent virtual $10,000 balance (not a shared pool split 5 ways). This allows fair, apples-to-apples comparison between strategies. Total virtual capital under management: $50,000.
- **Notification channel:** Pushbullet (`pushbullet.py` library, Note push type). Evaluated against ntfy.sh (zero-signup alternative) but Pushbullet was chosen because the user already has it in mind, likely has the app installed, and daily-frequency usage (~30 pushes/month) is comfortably within Pushbullet's free tier.
- **Runtime environment:** Oracle Cloud Free Tier VM (Ubuntu), managed as a systemd service. The assistant will produce the code, systemd unit, and setup script/instructions; the user (or the assistant if given SSH access) provisions and deploys the VM.
- **Trading style:** Live forward paper-trading against real-time prices — not historical backtesting.

## 3. Architecture

Single Python process (not one process/container per agent — see trade-off note below), structured into clearly separated modules that communicate through small interfaces:

```
trade-bot-sim/
├── data/           # MarketDataClient: Binance REST wrapper (candles, current prices)
├── portfolio/      # Portfolio: per-agent cash/positions/trade history, P&L math
├── strategies/      # BaseStrategy interface + 5 concrete strategy implementations
├── engine/         # SimulationEngine: orchestrates tick execution per agent
├── scheduler/      # APScheduler jobs: hourly tick, daily 00:00 Istanbul report job
├── reporting/      # Builds the daily text report from portfolio states
├── notifier/       # PushbulletNotifier wrapper
├── storage/        # SQLite persistence layer (portfolios, trades, daily reports)
├── config.py       # Watchlist, capital, strategy params, env-based secrets
├── main.py         # Wires everything together, starts scheduler, keeps process alive
└── deploy/         # systemd unit file, VM setup script, README
```

**Why one process, not one process/container per agent:** Oracle's free-tier VM shapes are resource-constrained (limited vCPU/RAM). Five containers would add Docker overhead for no real benefit at this scale. Instead, isolation between agents is achieved in-process: each agent's state (portfolio, positions, trade log) is fully independent, and each agent's tick execution is wrapped in its own try/except so one agent's failure (e.g. a strategy bug or a bad API response) cannot crash or affect the others. `systemd` with `Restart=always` is the outer safety net if the whole process dies.

**Data flow per tick (hourly):**
1. Scheduler fires → engine wakes up
2. `MarketDataClient` fetches latest 1h candles for the watchlist
3. For each of the 5 agents (isolated try/except per agent):
   - Strategy consumes candle history → emits a `Signal` (BUY/SELL/HOLD, symbol, size)
   - Engine applies risk rules (position size cap, stop-loss) and simulates the fill (with a realistic ~0.1% fee, matching Binance spot taker fee) against the current price
   - `Portfolio` is updated and persisted to SQLite; the trade is logged
4. Errors are logged; a failed agent simply skips this tick and is retried next tick

**Data flow for the daily report (00:00 Europe/Istanbul):**
1. Scheduler fires the daily job
2. `reporting` module reads all 5 portfolios' current and historical state from SQLite
3. Builds a clean plain-text summary (per-agent balance, daily P&L $/%, total P&L $/% since inception, open positions, trade count today, win rate, plus an overall ranking by total return)
4. Report is persisted (so history is queryable later) and pushed via `PushbulletNotifier`

## 4. The 5 Agents / Strategies

Chosen to cover distinct market regimes (trending, ranging, volatile) so the 5 agents are expected to behave differently rather than being redundant:

1. **Trend Follower** — EMA(9)/EMA(21) crossover entries, ATR-based stop-loss and position sizing.
2. **Mean Reversion** — RSI(14) + Bollinger Bands(20, 2): buys near the lower band when oversold, sells near the upper band when overbought.
3. **Momentum Breakout** — MACD crossover confirmed by volume.
4. **ML Predictor** — scikit-learn model (Gradient Boosting or Logistic Regression) trained on engineered features (returns, RSI, MACD, rolling volatility, volume z-score) to predict next-period direction probability. Retrained on a rolling window on a weekly cadence. Trades when predicted probability crosses a confidence threshold.
5. **Grid Trader** — Places buy/sell levels at fixed price intervals around the current price, designed to profit in range-bound/sideways conditions rather than trending ones.

**Shared risk rules (apply to all 5 agents):**
- Max ~25-30% of portfolio value per single position
- Stop-loss per position
- Simulated trading fee (~0.1%) applied to every simulated fill for realism
- No leverage — spot-only simulation

## 5. Persistence & Reliability

- **SQLite** stores: each agent's portfolio (cash, open positions), full trade history, and daily report history. This is what allows the process to restart (VM reboot, crash, deploy) without losing simulated state.
- **API failures:** retry with backoff on transient Binance API errors; if data still can't be fetched, the tick is skipped for that cycle and retried next cycle.
- **Per-agent isolation:** exceptions inside one agent's tick handling are caught and logged; they never propagate to other agents or crash the process.
- **Process-level safety net:** systemd unit configured with `Restart=always` so an unhandled crash brings the service back up automatically.

## 6. Reporting & Notification

- **Trigger:** Daily APScheduler job fixed to `Europe/Istanbul` timezone, firing at 00:00.
- **Channel:** Pushbullet "Note" push (title + plain-text body) via `pushbullet.py`, using an access token supplied through environment configuration (not committed to source).
- **Content:** Per-agent balance, daily and cumulative P&L ($ and %), open positions, today's trade count, win rate, and an overall ranking of the 5 agents by total return.
- **History:** Every generated report is also written to SQLite (and/or a flat log file) so historical daily reports can be reviewed later, independent of Pushbullet's own message retention.

## 7. Testing

- `pytest` unit tests for:
  - Portfolio math (buy/sell fills, fee application, P&L calculation) — the highest-risk area for silent correctness bugs
  - Each strategy's signal generation against fixture candle data (known inputs → expected signal)
  - Report text formatting (given known portfolio states → expected report content)
- No live-network tests in the automated suite; `MarketDataClient` is mocked/faked in tests.

## 8. Deployment

- Target: Oracle Cloud Free Tier VM (Ubuntu).
- Assistant deliverables: application code, `requirements.txt`, a systemd unit file, a VM setup script (Python install, dependency install, env file template), and a README with step-by-step deployment instructions.
- Secrets (Pushbullet access token) are supplied via an environment file on the VM, never committed to the repository.

## 9. Explicit Non-Goals

- No real order execution, no exchange API keys for trading (market-data-only, unauthenticated endpoints).
- No historical backtesting engine — this is forward/live paper-trading only.
- No web dashboard/UI — reporting is delivered via Pushbullet push notification plus persisted history in SQLite.
- No multi-exchange support — Binance only for this version.
