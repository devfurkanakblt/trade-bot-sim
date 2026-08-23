import datetime
import threading


class LiveState:
    """Thread-safe canlı bot durumu. Motor yazar, web sunucusu okur."""

    def __init__(self):
        self._lock = threading.Lock()
        self._agents: dict[str, dict] = {}
        self._candles: dict[str, list[dict]] = {}
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
        mode: str = "SPOT",
        leverage: int = 1,
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
                "mode": mode,
                "leverage": leverage,
                "updated_at": now,
            }
            self._updated_at = now

    def update_candles(self, candles_by_symbol: dict[str, list[dict]]) -> None:
        with self._lock:
            self._candles = {
                symbol: [{"t": c["open_time"], "c": c["close"]} for c in candles]
                for symbol, candles in candles_by_symbol.items()
            }

    def candles_snapshot(self) -> dict:
        with self._lock:
            return {symbol: [dict(p) for p in series] for symbol, series in self._candles.items()}

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
