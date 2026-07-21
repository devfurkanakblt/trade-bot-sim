import pytest

from src.portfolio.portfolio import Portfolio


def test_buy_reduces_cash_and_creates_position():
    p = Portfolio(10_000.0)
    p.buy("BTCUSDT", price=100.0, cash_amount=1000.0)
    assert p.cash == pytest.approx(9000.0)
    assert "BTCUSDT" in p.positions
    assert p.positions["BTCUSDT"].quantity == pytest.approx(9.99)  # (1000 - 0.1% fee) / 100


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
    # first buy: 9.99 @ 100, second buy: 4.995 @ 200
    expected_qty = 9.99 + 4.995
    expected_avg = (100.0 * 9.99 + 200.0 * 4.995) / expected_qty
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
