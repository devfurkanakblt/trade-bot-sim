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


def test_empty_candles_snapshot():
    state = LiveState()
    assert state.candles_snapshot() == {}


def test_update_candles_keeps_time_and_close_series():
    state = LiveState()
    state.update_candles(
        {
            "BTCUSDT": [
                {"open_time": 1000, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 9.0},
                {"open_time": 2000, "open": 1.5, "high": 3.0, "low": 1.0, "close": 2.5, "volume": 8.0},
            ]
        }
    )
    snap = state.candles_snapshot()
    assert snap == {"BTCUSDT": [{"t": 1000, "c": 1.5}, {"t": 2000, "c": 2.5}]}


def test_update_candles_overwrites_previous_series():
    state = LiveState()
    state.update_candles({"BTCUSDT": [{"open_time": 1000, "close": 1.5}]})
    state.update_candles({"BTCUSDT": [{"open_time": 2000, "close": 2.5}]})
    assert state.candles_snapshot() == {"BTCUSDT": [{"t": 2000, "c": 2.5}]}
