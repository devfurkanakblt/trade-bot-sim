from src.web.dashboard import create_app
from src.web.live_state import LiveState
from src.storage.db import init_db, log_trade


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


def test_health_endpoint_reports_service_is_up():
    response = _client().get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_index_returns_html():
    client = _client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.content_type
    assert b"/api/state" in resp.data  # sayfa JSON endpoint'ini poll ediyor
    assert b"/api/candles" in resp.data  # sayfa candle endpoint'ini de poll ediyor
    assert b"/results" in resp.data


def test_api_candles_returns_series_json():
    state = LiveState()
    state.update_candles({"BTCUSDT": [{"open_time": 1000, "close": 1.5}]})
    app = create_app(state)
    app.config.update(TESTING=True)
    resp = app.test_client().get("/api/candles")
    assert resp.status_code == 200
    assert resp.get_json() == {"BTCUSDT": [{"t": 1000, "c": 1.5}]}


def test_results_page_and_api_show_live_state_and_persisted_trades():
    state = LiveState()
    state.update_agent("scalper", "BUY", "BTCUSDT", 12.0, 0.12, 8000.0, 10012.0, {})
    conn = init_db(":memory:")
    log_trade(conn, "scalper", "BTCUSDT", "BUY", 0.1, 100000.0, 4.0, "2026-08-19T10:00:00")
    app = create_app(state, storage_conn=conn)
    app.config.update(TESTING=True)
    client = app.test_client()

    page = client.get("/results")
    assert page.status_code == 200
    assert b"Bot Sonuclari" in page.data
    assert b"/api/results" in page.data

    data = client.get("/api/results").get_json()
    assert data["state"]["agents"][0]["name"] == "scalper"
    assert data["trades"][0]["symbol"] == "BTCUSDT"
