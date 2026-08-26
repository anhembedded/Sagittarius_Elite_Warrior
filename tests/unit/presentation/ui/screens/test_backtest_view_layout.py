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
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import Tone
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view_model import (
    BackTestViewModel,
)


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
            "positionLabel": "vị thế mua",
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

    vm.set_stat_cards(_stat_cards(4), [])
    qapp.processEvents()

    assert v.top_widget._stat_cards_row.isVisible() is True
    assert v.top_widget._result_box.isVisible() is False
    card = v.top_widget._stat_cards_row.layout().itemAt(0).widget()
    assert card.objectName() == "cardMetric_0"


def test_top_panel_result_warning_line_does_not_affect_stat_cards_visibility(
    view, qapp
):
    """BOT-079 follow-up: the warning line shares the metrics-header row —
    setting it must not toggle the stat-cards-vs-result-box state."""
    v, vm = view
    vm.set_stat_cards(_stat_cards(4), [])
    qapp.processEvents()

    vm.set_result_warning_text("⚠ Phí giao dịch chiếm phần lớn kết quả.")
    qapp.processEvents()

    assert v.top_widget._stat_cards_row.isVisible() is True
    assert v.top_widget._result_warning_label.text() == (
        "⚠ Phí giao dịch chiếm phần lớn kết quả."
    )


def test_progress_banner_is_visible_while_backtest_runs(view, qapp):
    v, vm = view
    assert v.top_widget._progress_banner.isVisible() is False

    vm.set_backtest_progress(42.0, "Chạy toàn bộ dữ liệu: 42% · ETA ~8s")
    vm.set_ui_mode("RUNNING")
    qapp.processEvents()

    assert v.top_widget._progress_banner.isVisible() is True


def test_sync_progress_and_coverage_warning_are_visible(view, qapp):
    v, vm = view

    vm.set_data_coverage(False, "Thiếu nến từ 2026-01-01 00:00 UTC.")
    vm.set_needs_data_sync(True)
    vm.set_sync_progress(45.0, "Đang đồng bộ nến: 45/100 (45%)")
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
    vm.set_trade_log_page_state(_trade_log_rows(20), 75, 4)
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
            "Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.plot_layout.qt_platform_name",
            return_value="offscreen",
        ),
        patch(
            "Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.plot_layout.is_headless_qt_platform",
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
