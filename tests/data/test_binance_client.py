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
