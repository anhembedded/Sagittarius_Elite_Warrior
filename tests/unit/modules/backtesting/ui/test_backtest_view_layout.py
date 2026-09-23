"""Tests for `BackTestView`'s panel sizing (BOT-089, BOT-090) — rewritten
for EPIC-006E (QtWidgets `BackTestTopPanel`/`BackTestTradeLogsPanel`
replacing the QQuickWidget-hosted QML pair).

BOT-089/BOT-090's original problem (a hardcoded panel height/a splitter
free to squeeze the trade log pane below what it needs) doesn't need the
`implicitHeight`-read-back plumbing QML required anymore — a plain
`QWidget`'s own layout reports a correct `sizeHint()`/`minimumSizeHint()`
without help, and `BackTestTradeLogsPanel.minimum_usable_height()`
computes BOT-090's floor directly in Python. These tests assert the
same INVARIANTS the QML-era tests did, just via direct widget attributes
instead of `qml_item()`/`rootObject()`.
"""

from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view_model import (
    BackTestViewModel,
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


def _trade_log_rows(count: int) -> list[dict[str, str]]:
    return [
        {
            "index": str(i + 1),
            "positionLabel": "long position",
            "entryTimeText": "2026-08-01 10:00",
            "entryPriceText": "1000.00",
            "exitPriceText": "1010.00",
            "exitTimeText": "2026-08-01 11:00",
            "positionSizeText": "100.00",
            "quantityText": "0.1",
            "pnlText": "+10.00",
            "returnText": "+1.00%",
            "pnlColor": "#26a69a",
            "entryReasonText": "",
            "exitReasonText": "",
            "durationText": "",
            "metadataItems": [],
        }
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


def test_progress_banner_is_visible_while_backtest_runs(view, qapp):
    v, vm = view
    assert v.top_widget._progress_banner.isVisible() is False

    vm.run_progress.set_backtest_progress(42.0, "Running full dataset: 42% · ETA ~8s")
    vm.set_ui_mode("RUNNING")
    qapp.processEvents()

    assert v.top_widget._progress_banner.isVisible() is True


def test_sync_progress_and_coverage_warning_are_visible(view, qapp):
    v, vm = view

    vm.run_result.set_data_coverage(False, "Missing candles from 2026-01-01 00:00 UTC.")
    vm.run_result.set_needs_data_sync(True)
    vm.run_progress.set_sync_progress(45.0, "Syncing candles: 45/100 (45%)")
    vm.set_ui_mode("SYNCING")
    qapp.processEvents()

    assert v.top_widget._progress_banner.isVisible() is True
    assert v.top_widget._coverage_banner.isVisible() is True


def test_trade_log_pane_never_shrinks_below_its_usable_minimum(view):
    """BUG-004's exact symptom — header/tabs/pagination all rendered, table
    body empty — was the splitter squeezing the pane below what the table
    needs. `set_view_model()` applies `minimum_usable_height()` via
    `setMinimumHeight()`, so the splitter can never go below it."""
    v, _vm = view

    assert v.bottom_widget.minimumHeight() >= v.bottom_widget.minimum_usable_height()


def test_trade_log_rows_are_visible_by_default(view, qapp):
    """Regression guard for BUG-004/BOT-090: a 75-trade result page
    (PAGE_SIZE=20 rows) rendered with zero rows actually visible."""
    v, vm = view
    vm.trade_log.set_page_state(_trade_log_rows(20), 75, 4)
    qapp.processEvents()

    assert v.bottom_widget._rows_layout.count() == 21  # 20 rows + trailing stretch
    first_row = v.bottom_widget._rows_layout.itemAt(0).widget()
    assert first_row._summary_btn.objectName() == "rowTradeLog_1"


def test_backtest_chart_fps_overlay_follows_dev_mode(qapp, request):
    v = BackTestView()
    request.addfinalizer(v.deleteLater)

    v.set_chart_dev_mode(True)
    cards = v.render_symbol_cards(["BTCUSDT"])

    assert cards[0].chart_card.fps_overlay.is_enabled is True
    assert cards[0].chart_card.fps_overlay.label.isHidden() is False

    v.set_chart_dev_mode(False)

    assert cards[0].chart_card.fps_overlay.is_enabled is False
    assert cards[0].chart_card.fps_overlay.label.isHidden() is True


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
    test_chart_canvas_view.py for that pure-function coverage)."""
    from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.chart_canvas_view import (
        MarkerOutcomeFilter,
    )

    v = BackTestView()
    request.addfinalizer(v.deleteLater)
    v.render_symbol_cards(["ETHUSDT"])
    v.on_backtest_data_ready(_win_loss_result(), [], [])

    assert len(v._filtered_trade_flag_markers()) == 4  # 2 trades x entry+exit

    wins_only_index = v.chart_controls._marker_outcome_combo.findData(
        MarkerOutcomeFilter.WINS_ONLY
    )
    v.chart_controls._marker_outcome_combo.setCurrentIndex(wins_only_index)

    assert len(v._filtered_trade_flag_markers()) == 2  # only the winning trade


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
