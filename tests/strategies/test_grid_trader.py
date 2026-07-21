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
