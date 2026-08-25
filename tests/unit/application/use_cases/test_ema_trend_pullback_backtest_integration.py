"""BOT-111 — end-to-end wiring proof for the golden reference strategy:
real EmaTrendPullbackStrategy + real RunStaticBacktestCommandHandler ->
real BacktestResult -> real chart-line colors and trade markers. Individual
pieces (color override precedence, side/TP-aware marker labels, native
label dispatch) already have precise unit coverage elsewhere; this test's
job is only to prove the pipeline is actually wired together correctly,
not to re-verify each piece's own logic in isolation."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_static_backtest import (
    RunStaticBacktestCommand,
    RunStaticBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.exit_reason import ExitReason
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.strategies.ema_trend_pullback_strategy import (
    EmaTrendPullbackStrategy,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.chart_canvas_view import (
    trade_flag_markers,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.strategy_indicator_lines import (
    assign_strategy_line_colors,
    compute_strategy_indicator_lines,
)

_STRATEGY_KEY = "ema_trend_confirm_pullback"
_PARAMS = {
    "ema_long_len": 12,
    "tick_confirm": 3,
    "touch_sensitivity": 0.0,
    "enable_touch_reset": True,
    "enable_touch_exit": True,
    "ema_entry_len": 10,
    "pullback_sensitivity": 1.0,
    "candle_confirm_entry": False,
    "take_profit_percent": 2.0,
    "enable_alerts": True,
}
_WARMUP_BARS = 14


def _candle(
    index: int, open_: float, high: float, low: float, close: float
) -> MarketData:
    open_time = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(minutes=index)
    return MarketData(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_MINUTE.value,
        open_time=open_time,
        open_price=open_,
        high_price=high,
        low_price=low,
        close_price=close,
        volume=1000.0,
        close_time=open_time + timedelta(minutes=1),
        quote_asset_volume=close * 1000.0,
        number_of_trades=10,
        taker_buy_base_asset_volume=500.0,
        taker_buy_quote_asset_volume=500.0 * close,
    )


def _flat(index: int, price: float) -> MarketData:
    return _candle(index, price, price, price, price)


def _klines_with_one_confirmed_long_trade() -> list[MarketData]:
    """Same warmup+pullback shape `test_ema_trend_pullback_strategy.py`'s
    own `test_uptrend_confirms_and_a_pullback_bar_fires_buy` hand-verifies
    fires a real BUY — extended with a few more bars (filling the entry,
    then a sharp reversal) so the run produces one complete, closed `Trade`
    to render, not just a still-open position. Exact resulting trade
    (entry 362.0, exit 187.0, END_OF_BACKTEST) confirmed by actually running
    this through the real handler, not hand-derived."""
    ramp = [_flat(i, 100.0 + 20.0 * i) for i in range(_WARMUP_BARS)]
    last_close = ramp[-1].close_price
    pullback = _candle(
        _WARMUP_BARS, last_close, last_close + 5.0, last_close - 80.0, last_close + 2.0
    )
    post = pullback.close_price
    return [
        *ramp,
        pullback,
        _candle(_WARMUP_BARS + 1, post, post + 10.0, post, post + 8.0),
        _candle(_WARMUP_BARS + 2, post + 8.0, post + 15.0, post + 5.0, post + 12.0),
        _candle(_WARMUP_BARS + 3, post + 12.0, post + 12.0, 0.0, (post + 12.0) * 0.5),
    ]


def _run_real_backtest() -> tuple:
    klines = _klines_with_one_confirmed_long_trade()
    repo = Mock()
    # BUG-025: RunStaticBacktestCommandHandler streams via count_klines()/
    # stream_klines() instead of get_klines() — mirror that contract here
    # against this test's static `klines` list.
    repo.count_klines.side_effect = lambda **kwargs: (
        len(klines)
        if kwargs.get("limit") is None
        else min(kwargs["limit"], len(klines))
    )
    repo.stream_klines.side_effect = lambda **kwargs: iter(
        klines[kwargs.get("offset") or 0 :][: kwargs.get("limit")]
    )
    registry = StrategyRegistry()
    registry.register(_STRATEGY_KEY, EmaTrendPullbackStrategy)
    handler = RunStaticBacktestCommandHandler(
        repository=repo, strategy_registry=registry, event_publisher=Mock()
    )
    command = RunStaticBacktestCommand(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_MINUTE,
        strategy_key=_STRATEGY_KEY,
        strategy_params=_PARAMS,
        initial_balance=10_000.0,
        fee_percent=0.0,
    )
    result = handler.execute(command)
    return result, klines


def test_real_run_produces_exactly_the_hand_verified_long_trade():
    result, _ = _run_real_backtest()

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.side is PositionSide.LONG
    assert trade.entry_price == 362.0
    assert trade.exit_reason is ExitReason.END_OF_BACKTEST


def test_real_result_produces_truthful_long_markers_via_the_real_pipeline():
    result, _ = _run_real_backtest()

    markers = trade_flag_markers(result)

    assert len(markers) == 2
    entry_marker, exit_marker = markers
    assert entry_marker[2] == "MUA (LONG)"
    assert exit_marker[2] == "ĐÓNG LONG"
    # Truthful markers (BOT-096): never mislabel a long trade as short/sell.
    assert "SHORT" not in entry_marker[2].upper()
    assert "SHORT" not in exit_marker[2].upper()


def test_real_strategy_indicator_lines_use_the_strategys_own_reference_colors():
    result, klines = _run_real_backtest()
    strategy = EmaTrendPullbackStrategy(_PARAMS)

    lines = compute_strategy_indicator_lines(strategy, klines)
    colors = assign_strategy_line_colors(
        list(lines.keys()), strategy.chart_line_colors()
    )

    assert set(lines.keys()) == {
        EmaTrendPullbackStrategy.EMA_LONG_KEY,
        EmaTrendPullbackStrategy.EMA_ENTRY_KEY,
    }
    assert colors[EmaTrendPullbackStrategy.EMA_LONG_KEY] == "#f6465d"
    assert colors[EmaTrendPullbackStrategy.EMA_ENTRY_KEY] == "#2962ff"
    # Every line actually has real points to draw (not an empty series that
    # would silently render nothing).
    for x_data, y_data in lines.values():
        assert len(x_data) == len(y_data) > 0
    assert result.trades  # sanity: this run really did produce a trade
