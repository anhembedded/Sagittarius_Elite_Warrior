"""Tests for `BackTestView`'s panel sizing (BOT-089, BOT-090) — rewritten
for EPIC-006E (QtWidgets `BackTestTopPanel`/`BackTestTradeLogsPanel`
replacing the QQuickWidget-hosted QML pair).

BOT-089/BOT-090's original problem (a hardcoded panel height/a splitter
free to squeeze the trade log pane below what it needs) doesn't need the
`implicitHeight`-read-back plumbing QML required anymore — a plain
`QWidget`'s own layout reports a correct `sizeHint()`/`minimumSizeHint()`
without help. Since `EPIC-033L` the trades are a table in a dock that
scrolls at any height, so BOT-090's computed floor is gone; these tests
assert the same invariant — rows visible — on the table.
"""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.trade_log_row import (
    TradeLogRow,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import Tone


def _stat_cards(count: int) -> list[dict[str, str]]:
    return [
        {
            "title": f"Card {i}",
            "value": "1.00",
            "valueTone": Tone.NEUTRAL,
            "suffix": "USD",
            "badgeText": "",
            "badgeTone": Tone.NEUTRAL,
        }
        for i in range(count)
    ]


def _trade_log_rows(count: int) -> list[TradeLogRow]:
    moment = datetime(2026, 8, 1, 10, tzinfo=UTC)
    return [
        TradeLogRow(i + 1, moment, 1000.0, moment, 1010.0, 0.1, 1.0, 1.0)
        for i in range(count)
    ]


@pytest.fixture
def view(qapp, request):
    v = BackTestView()
    vm = BackTestViewModel()
    v.set_view_model(vm)
    v.resize(1400, 900)
    v.show()
    qapp.processEvents()
    request.addfinalizer(v.deleteLater)
    return v, vm


def test_stat_cards_row_replaces_result_box_when_a_run_completes(view, qapp):
    v, vm = view
    assert v.top_widget._stat_cards_row.isVisible() is False
    assert v.top_widget._result_box.isVisible() is True

    vm.run_result.set_stat_cards(_stat_cards(4), [])
    qapp.processEvents()

    assert v.top_widget._stat_cards_row.isVisible() is True
    assert v.top_widget._result_box.isVisible() is False
    # `EPIC-025` PR 4.3g: a `QWidget` again, reachable by `findChild` — the
    # name is unchanged from every previous version of this row.
    assert v.top_widget._stat_cards_row.findChild(QWidget, "cardMetric_0") is not None


def test_metrics_header_and_expand_button_appear_when_a_run_completes(view, qapp):
    """A completed run with no out-of-sample warning never touches
    resultWarningText — `_sync_metrics_header` must still run off
    `statCardsChanged` alone, or `_metrics_header` (title bar + the "Mở
    rộng chỉ số chi tiết" button opening `MetricsDetailModal`) stays
    permanently hidden even though the stat cards row right below it is
    visible. Reproduces a real user report: the Expand section was
    nowhere to be found after running a backtest."""
    v, vm = view
    assert v.top_widget._metrics_header.isVisible() is False

    vm.run_result.set_stat_cards(_stat_cards(4), [])
    qapp.processEvents()

    assert v.top_widget._metrics_header.isVisible() is True
    assert v.top_widget._btn_expand_metrics.isVisible() is True


def test_top_panel_result_warning_line_does_not_affect_stat_cards_visibility(
    view, qapp
):
    """BOT-079 follow-up: the warning line shares the metrics-header row —
    setting it must not toggle the stat-cards-vs-result-box state."""
    v, vm = view
    vm.run_result.set_stat_cards(_stat_cards(4), [])
    qapp.processEvents()

    vm.run_result.set_result_warning_text("⚠ Trading fees make up most of the result.")
    qapp.processEvents()

    assert v.top_widget._stat_cards_row.isVisible() is True
    assert v.top_widget._result_warning_label.text() == (
        "⚠ Trading fees make up most of the result."
    )


def test_sync_progress_and_coverage_warning_are_visible(view, qapp):
    v, vm = view

    vm.run_result.set_data_coverage(False, "Missing candles from 2026-01-01 00:00 UTC.")
    vm.run_result.set_needs_data_sync(True)
    vm.run_progress.set_sync_progress(45.0, "Syncing candles: 45/100 (45%)")
    vm.set_ui_mode("SYNCING")
    qapp.processEvents()

    # The sync's progress is the status bar's (`EPIC-033L`); the coverage
    # warning stays with the figures it qualifies.
    assert not v.status_widgets()[0].isHidden()
    assert v.top_widget._coverage_banner.isVisible() is True


def test_trade_rows_are_visible_by_default(view, qapp):
    """Regression guard for BUG-004/BOT-090: a 75-trade result rendered its
    header and pager with zero rows actually visible, the pane squeezed
    below what the hand-built rows needed. The Trades table (`EPIC-033L`)
    lists every trade and scrolls; at the mode's default layout its first
    row is on screen in full."""
    v, vm = view
    vm.trade_log.set_rows(_trade_log_rows(75))
    qapp.processEvents()
    table = v.bottom_widget.table.view

    assert table.model().rowCount() == 75
    assert table.rowAt(0) == 0
    assert table.viewport().height() >= table.rowHeight(0)


def test_backtest_chart_fps_meter_follows_dev_mode(qapp, request):
    v = BackTestView()
    request.addfinalizer(v.deleteLater)

    v.set_chart_dev_mode(True)
    cards = v.render_symbol_cards(["BTCUSDT"])

    assert cards[0].chart_card.fps_meter.is_enabled is True
    assert cards[0].chart_card.fps_meter.label.isHidden() is False

    v.set_chart_dev_mode(False)

    assert cards[0].chart_card.fps_meter.is_enabled is False
    assert cards[0].chart_card.fps_meter.label.isHidden() is True


def test_backtest_requests_opengl_for_current_and_future_chart_cards(qapp, request):
    v = BackTestView()
    request.addfinalizer(v.deleteLater)

    v.set_chart_opengl_enabled(True)
    with (
        patch(
            "Sagittarius_Elite_Warrior.src.support.charting.chart_card.plot_layout.qt_platform_name",
            return_value="offscreen",
        ),
        patch(
            "Sagittarius_Elite_Warrior.src.support.charting.chart_card.plot_layout.is_headless_qt_platform",
            return_value=True,
        ),
    ):
        cards = v.render_symbol_cards(["BTCUSDT"])

    assert cards[0].chart_card.plot_layout.opengl_requested is True
    # pytest uses the offscreen Qt platform, so the safety fallback must win.
    assert cards[0].chart_card.plot_layout.render_backend == "cpu"


def test_backtest_enables_cached_interaction_for_future_chart_cards(qapp, request):
    v = BackTestView()
    request.addfinalizer(v.deleteLater)

    v.set_chart_cached_interaction_enabled(True)
    cards = v.render_symbol_cards(["BTCUSDT"])

    assert cards[0].chart_card.cached_interaction is not None


def _win_loss_result():
    from datetime import UTC, datetime

    from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_metrics import (
        BacktestMetrics,
    )
    from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
        BacktestResult,
    )
    from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.trade import Trade

    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    t1 = datetime(2026, 1, 2, tzinfo=UTC)
    win = Trade(
        symbol="ETHUSDT",
        entry_time=t0,
        entry_price=100.0,
        exit_time=t1,
        exit_price=110.0,
        quantity=1.0,
        pnl=10.0,
        pnl_percent=10.0,
        fees_paid=0.0,
    )
    loss = Trade(
        symbol="ETHUSDT",
        entry_time=t0,
        entry_price=100.0,
        exit_time=t1,
        exit_price=90.0,
        quantity=1.0,
        pnl=-10.0,
        pnl_percent=-10.0,
        fees_paid=0.0,
    )
    equity_curve = [(t0, 1000.0), (t1, 1000.0)]
    return BacktestResult(
        symbol="ETHUSDT",
        initial_balance=1000.0,
        final_balance=1000.0,
        trades=[win, loss],
        equity_curve=equity_curve,
        metrics=BacktestMetrics.compute([win, loss], equity_curve, 1000.0),
    )


def test_marker_filters_narrow_the_trade_flag_markers_drawn(qapp, request):
    """PROP-004 end-to-end: `chart_controls`'s outcome filter actually
    changes what `_filtered_trade_flag_markers()` returns, not just what
    `filter_trades_for_markers()` returns in isolation (see
    test_chart_canvas_view.py for that pure-function coverage). Asserts
    presence of each trade's own exit marker rather than a bare count
    (`pitfalls/tests.md` §3) — the win/loss entry markers are identical
    (same entry time/price), so the exit marker is what actually proves
    which trade survived the filter."""
    from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.chart_canvas_view import (
        _LONG_EXIT_LABEL,
        MarkerOutcomeFilter,
    )
    from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import (
        BEAR_COLOR,
    )

    v = BackTestView()
    request.addfinalizer(v.deleteLater)
    v.render_symbol_cards(["ETHUSDT"])
    result = _win_loss_result()
    win_trade, loss_trade = result.trades
    v.on_backtest_data_ready(result, [], [])

    win_exit_marker = (
        win_trade.exit_time.timestamp(),
        win_trade.exit_price,
        _LONG_EXIT_LABEL,
        BEAR_COLOR,
        "down",
    )
    loss_exit_marker = (
        loss_trade.exit_time.timestamp(),
        loss_trade.exit_price,
        _LONG_EXIT_LABEL,
        BEAR_COLOR,
        "down",
    )

    unfiltered_markers = v._filtered_trade_flag_markers()
    assert win_exit_marker in unfiltered_markers
    assert loss_exit_marker in unfiltered_markers

    wins_only_index = v.chart_controls._marker_outcome_combo.findData(
        MarkerOutcomeFilter.WINS_ONLY
    )
    v.chart_controls._marker_outcome_combo.setCurrentIndex(wins_only_index)

    wins_only_markers = v._filtered_trade_flag_markers()
    assert win_exit_marker in wins_only_markers
    assert loss_exit_marker not in wins_only_markers


def test_render_chart_passes_pnl_badges_alongside_trade_markers(qapp, request):
    """`PROP-003` wiring: `_render_chart()` must forward
    `_filtered_trade_flag_badges()` to `set_script_markers()` alongside
    the markers, positionally aligned."""
    from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.chart_canvas_view import (
        trade_marker_badges_for_trades,
    )

    v = BackTestView()
    request.addfinalizer(v.deleteLater)
    v.render_symbol_cards(["ETHUSDT"])
    result = _win_loss_result()
    card = v._current_card()

    with patch.object(card, "set_script_markers") as spy:
        v.on_backtest_data_ready(result, [], [])

    spy.assert_called_once()
    _, call_args, call_kwargs = spy.mock_calls[0]
    badges = call_args[2] if len(call_args) > 2 else call_kwargs.get("badges")
    assert badges == trade_marker_badges_for_trades(result.trades)
    assert any(badge is not None for badge in badges)


def test_refresh_trade_flag_filters_reapplies_the_checkboxs_own_state(qapp, request):
    """A filter changing must never override the separate Buy/Sell Flags
    show/hide toggle — it only re-applies whatever that toggle already
    says (`set_trade_flags_visible`'s own contract)."""
    v = BackTestView()
    request.addfinalizer(v.deleteLater)
    v.render_symbol_cards(["ETHUSDT"])
    v.chart_controls._trade_flags_check.setChecked(False)

    with patch.object(v, "set_trade_flags_visible") as spy:
        v.refresh_trade_flag_filters()

    spy.assert_called_once_with(False)
