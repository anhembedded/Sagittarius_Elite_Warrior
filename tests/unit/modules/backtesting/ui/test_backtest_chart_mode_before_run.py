"""BUG-158: the chart-view bar changes the chart before a run has a result.

`BackTestView.set_chart_mode()` re-rendered only once `_last_result` existed,
so Equity curve and Side by side left the price chart untouched in the state
the user is in before (or after a failed) run.
"""

from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.chart_canvas_view import (
    ChartDisplayMode,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.chart_type_renderer import (
    CANDLESTICK,
    LINE,
)


def _view_with_a_chart(qapp, request) -> BackTestView:
    view = BackTestView()
    request.addfinalizer(view.deleteLater)
    view.render_symbol_cards(["BTCUSDT"])
    return view


def _chart_type(view: BackTestView) -> str:
    return view.chart_cards[0].chart_card.chart_type_renderer.chart_type


def test_equity_mode_before_any_run_changes_the_chart_to_a_line(qapp, request):
    view = _view_with_a_chart(qapp, request)
    assert view._last_result is None

    view.set_chart_mode(ChartDisplayMode.EQUITY)

    assert _chart_type(view) == LINE


def test_side_by_side_before_any_run_adds_the_equity_pane(qapp, request):
    view = _view_with_a_chart(qapp, request)

    view.set_chart_mode(ChartDisplayMode.BOTH)

    assert view._equity_subplot_added is True
    assert _chart_type(view) == CANDLESTICK


def test_back_to_candlestick_removes_the_equity_pane(qapp, request):
    view = _view_with_a_chart(qapp, request)
    view.set_chart_mode(ChartDisplayMode.BOTH)

    view.set_chart_mode(ChartDisplayMode.OHLC)

    assert view._equity_subplot_added is False


def test_a_preview_refresh_keeps_the_chosen_chart_mode(qapp, request):
    view = _view_with_a_chart(qapp, request)
    view.set_chart_mode(ChartDisplayMode.EQUITY)

    view.on_preview_data_ready([], [])

    assert _chart_type(view) == LINE
