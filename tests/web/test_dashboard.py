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
