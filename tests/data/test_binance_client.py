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
            "close_time": 0,
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
    assert kwargs["headers"] is None


@patch("src.data.binance_client.requests.get")
def test_market_data_proxy_adds_authentication_header(mock_get):
    mock_get.return_value = make_response({"symbol": "BTCUSDT", "price": "123.45"})

    client = MarketDataClient(
        base_url="https://trade-bot-proxy.example.workers.dev/binance/",
        proxy_token="proxy-secret",
    )
    assert client.get_current_price("BTCUSDT") == 123.45

    mock_get.assert_called_once_with(
        "https://trade-bot-proxy.example.workers.dev/binance/api/v3/ticker/price",
        params={"symbol": "BTCUSDT"},
        headers={"X-Proxy-Token": "proxy-secret"},
        timeout=10,
    )


@patch("src.data.binance_client.time.time", return_value=100.0)
@patch("src.data.binance_client.requests.get")
def test_get_klines_excludes_currently_forming_candle(mock_get, _mock_time):
    raw = [
        [0, "100", "110", "90", "105", "10", 99_999, 0, 0, 0, 0, 0],
        [60_000, "105", "115", "100", "110", "11", 159_999, 0, 0, 0, 0, 0],
    ]
    mock_get.return_value = make_response(raw)

    candles = MarketDataClient().get_klines("BTCUSDT")

    assert [candle["open_time"] for candle in candles] == [0]


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


@patch("src.data.binance_client.requests.get")
def test_get_klines_raises_on_malformed_response_missing_fields(mock_get):
    """Test that malformed klines (missing fields) raises MarketDataError."""
    # Row missing required fields (only 3 elements instead of 12+)
    raw = [[1690000000000, "100.0", "110.0"]]
    mock_get.return_value = make_response(raw)

    client = MarketDataClient()
    with pytest.raises(MarketDataError) as exc_info:
        client.get_klines("BTCUSDT")

    assert "Failed to parse klines response" in str(exc_info.value)
    assert "BTCUSDT" in str(exc_info.value)


@patch("src.data.binance_client.requests.get")
def test_get_klines_raises_on_malformed_response_bad_float(mock_get):
    """Test that klines with non-numeric price raises MarketDataError."""
    # Row with a non-numeric value where float is expected
    raw = [[1690000000000, "not_a_number", "110.0", "90.0", "105.0", "12.5", 0, 0, 0, 0, 0, 0]]
    mock_get.return_value = make_response(raw)

    client = MarketDataClient()
    with pytest.raises(MarketDataError) as exc_info:
        client.get_klines("BTCUSDT")

    assert "Failed to parse klines response" in str(exc_info.value)
    assert "BTCUSDT" in str(exc_info.value)


@patch("src.data.binance_client.requests.get")
def test_get_current_price_raises_on_malformed_response_missing_price_key(mock_get):
    """Test that price response without 'price' key raises MarketDataError."""
    mock_get.return_value = make_response({"symbol": "BTCUSDT"})

    client = MarketDataClient()
    with pytest.raises(MarketDataError) as exc_info:
        client.get_current_price("BTCUSDT")

    assert "Failed to parse price response" in str(exc_info.value)
    assert "BTCUSDT" in str(exc_info.value)


@patch("src.data.binance_client.requests.get")
def test_get_current_price_raises_on_malformed_response_bad_float(mock_get):
    """Test that price response with non-numeric value raises MarketDataError."""
    mock_get.return_value = make_response({"symbol": "BTCUSDT", "price": "not_a_number"})

    client = MarketDataClient()
    with pytest.raises(MarketDataError) as exc_info:
        client.get_current_price("BTCUSDT")

    assert "Failed to parse price response" in str(exc_info.value)
    assert "BTCUSDT" in str(exc_info.value)


@patch("src.data.binance_client.requests.get")
def test_get_popular_usdt_pairs_ranks_volume_and_filters_leveraged_tokens(mock_get):
    mock_get.return_value = make_response([
        {"symbol": "ETHUSDT", "quoteVolume": "200"},
        {"symbol": "BTCUSDT", "quoteVolume": "300"},
        {"symbol": "BTCUPUSDT", "quoteVolume": "999999"},
        {"symbol": "EURUSDT", "quoteVolume": "0"},
        {"symbol": "BNBBUSD", "quoteVolume": "10000"},
    ])

    assert MarketDataClient().get_popular_usdt_pairs(limit=1) == ["BTCUSDT"]
