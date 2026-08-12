from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.chart_canvas_view import (
    ChartDisplayMode,
    equity_curve_to_candles,
    equity_curve_to_line_data,
    trade_flag_markers,
)

_T0 = datetime(2026, 1, 1, tzinfo=UTC)
_T1 = datetime(2026, 1, 2, tzinfo=UTC)


def test_chart_display_mode_has_exactly_the_3_bot_056_modes():
    assert {mode.value for mode in ChartDisplayMode} == {"ohlc", "equity", "both"}


def test_equity_curve_to_candles_flattens_ohlc_to_the_single_equity_value():
    equity_curve = [(_T0, 1000.0), (_T1, 1050.0)]

    candles = equity_curve_to_candles(equity_curve)

    assert candles == [
        (_T0.timestamp(), 1000.0, 1000.0, 1000.0, 1000.0),
        (_T1.timestamp(), 1050.0, 1050.0, 1050.0, 1050.0),
    ]


def test_equity_curve_to_line_data_splits_into_x_and_y_series():
    equity_curve = [(_T0, 1000.0), (_T1, 1050.0)]

    x_data, y_data = equity_curve_to_line_data(equity_curve)

    assert x_data == [_T0.timestamp(), _T1.timestamp()]
    assert y_data == [1000.0, 1050.0]


def _result_with_one_trade() -> BacktestResult:
    trade = Trade(
        symbol="ETHUSDT",
        entry_time=_T0,
        entry_price=100.0,
        exit_time=_T1,
        exit_price=110.0,
        quantity=1.0,
        pnl=10.0,
        pnl_percent=10.0,
        fees_paid=0.0,
    )
    metrics = BacktestMetrics.compute([trade], [(_T0, 1000.0), (_T1, 1010.0)], 1000.0)
    return BacktestResult(
        symbol="ETHUSDT",
        initial_balance=1000.0,
        final_balance=1010.0,
        trades=[trade],
        equity_curve=[(_T0, 1000.0), (_T1, 1010.0)],
        metrics=metrics,
    )


def test_trade_flag_markers_emits_one_buy_and_one_sell_per_trade():
    markers = trade_flag_markers(_result_with_one_trade())

    assert markers == [
        (_T0.timestamp(), 100.0, "Buy", BULL_COLOR, "up"),
        (_T1.timestamp(), 110.0, "Sell", BEAR_COLOR, "down"),
    ]


def test_trade_flag_markers_of_a_result_with_no_trades_is_empty():
    empty = BacktestResult(
        symbol="ETHUSDT",
        initial_balance=1000.0,
        final_balance=1000.0,
        trades=[],
        equity_curve=[(_T0, 1000.0)],
        metrics=BacktestMetrics.compute([], [(_T0, 1000.0)], 1000.0),
    )

    assert trade_flag_markers(empty) == []
