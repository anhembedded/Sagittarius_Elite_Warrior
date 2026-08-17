"""Tests for BackTestView's panel sizing (BOT-089, BOT-090).

BOT-089's root problem: the top QQuickWidget's height was a hardcoded
constant (`_TOP_PANEL_HEIGHT = 190`) that ignored what the QML content
actually needed — already bumped once before (120 -> 190) for the exact
same reason, when BOT-055's stat cards no longer fit. These tests assert
the INVARIANT the fix establishes (widget height always matches the QML's
own computed implicitHeight, and every row gets the space it actually
needs) rather than a specific pixel count or a "must grow" direction —
the "no result yet" placeholder and the "4 stat cards" states are sized
independently from each other (one isn't a strict subset of the other's
content), so which one is taller is an implementation detail, not
something to pin down here.

BOT-090 covers the bottom Trade Logs pane: `main_splitter.setSizes([600,
200])` was only ever an initial hint, and nothing stopped the splitter
from squeezing the pane far below what the table needs — the exact
BUG-004 symptom (header/tabs/pagination all rendered, zero trade rows
visible).
"""

import pytest
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
            "valueColor": "",
            "suffix": "USD",
            "badgeText": "",
            "badgeColor": "",
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
    v.load_qml()
    v.resize(1400, 900)
    v.show()
    qapp.processEvents()
    request.addfinalizer(v.deleteLater)
    return v, vm


def test_top_panel_height_always_matches_qml_implicit_height(view, qtbot):
    """The widget must never diverge from what the QML itself says it
    needs — no independent hardcoded number, in either direction."""
    v, _vm = view
    root = v.top_widget.rootObject()

    qtbot.waitUntil(
        lambda: v.top_widget.height() == int(root.property("implicitHeight")),
        timeout=2000,
    )


def test_stat_cards_are_not_clipped_once_rendered(view, qtbot, qml_item):
    """Regression guard for the exact failure mode in BUG-004/BOT-089: a
    fixed-height widget silently clipping the stat cards' value/badge row
    off (BOT-055's original bug) or the cards row entirely reporting 0
    height to its parent (the `Layout.fillHeight` bug this task's own
    investigation found and fixed). Waits for a real MetricCard QML object
    to exist rather than comparing heights before/after — the "no result
    yet" placeholder and the "has cards" state aren't ordered relative to
    each other, so an inequality on `top_widget.height()` alone can't tell
    "rendered correctly" from "rendered clipped".

    `cardMetric_0` is a `Repeater` item, so it's reachable only through the
    *visual* tree (`qml_item`, walking `childItems()`) — `findChild()`
    walks the QObject tree and never finds it, per this repo's own
    documented pitfall (`tests/conftest.py`)."""
    v, vm = view
    vm.set_stat_cards(_stat_cards(4), [])

    def first_card_is_fully_visible() -> bool:
        root = v.top_widget.rootObject()
        card = qml_item(root, "cardMetric_0")
        if card is None:
            return False
        # `card.y` alone is relative to its immediate parent (statCardsRow),
        # which stays visually correct even when clipped — the "y not
        # counted in the parent's implicitHeight" bug moves the RECTANGLE
        # itself down past the widget's bottom edge, only visible once
        # mapped into root/widget coordinates (verified against the actual
        # BUG-004 mutation: local y=0, absolute y=106, widget height=118 —
        # the local check alone would have missed it).
        absolute_y = card.mapToItem(root, 0, 0).y()
        card_bottom = absolute_y + card.property("height")
        return card_bottom <= v.top_widget.height()

    qtbot.waitUntil(first_card_is_fully_visible, timeout=2000)


def test_top_panel_height_is_unchanged_when_the_warning_line_appears(
    view, qtbot, qml_item
):
    """resultWarningText (BOT-079) deliberately shares the metrics-header
    row (right-aligned, reusing that row's existing `Layout.fillWidth`
    spacer) rather than occupying a row of its own — the QML comment above
    `lblResultWarning` spells this out: "costs 0 extra vertical space in
    BackTestTopPanel's fixed-height budget". Confirms BOT-089's dynamic
    sizing didn't silently undo BOT-079's intent."""
    v, vm = view
    root = v.top_widget.rootObject()
    vm.set_stat_cards(_stat_cards(4), [])
    qtbot.waitUntil(
        lambda: (
            qml_item(root, "cardMetric_0") is not None
            and v.top_widget.height() == int(root.property("implicitHeight"))
        ),
        timeout=2000,
    )
    height_before = v.top_widget.height()

    vm.set_result_warning_text("⚠ Phí giao dịch chiếm phần lớn kết quả.")
    qtbot.waitUntil(
        lambda: v.top_widget.height() == int(root.property("implicitHeight")),
        timeout=2000,
    )

    assert v.top_widget.height() == height_before


def test_progress_banner_is_visible_and_resized_while_backtest_runs(
    view, qtbot, qml_item
):
    v, vm = view
    root = v.top_widget.rootObject()
    banner = qml_item(root, "backtestProgressBanner")
    assert banner is not None
    assert banner.property("visible") is False

    vm.set_backtest_progress(42.0, "Chạy toàn bộ dữ liệu: 42% · ETA ~8s")
    vm.set_ui_mode("RUNNING")
    qtbot.waitUntil(
        lambda: (
            banner.property("visible") is True
            and v.top_widget.height() == int(root.property("implicitHeight"))
        ),
        timeout=2000,
    )


def test_sync_progress_and_coverage_warning_are_visible(view, qtbot, qml_item):
    v, vm = view
    root = v.top_widget.rootObject()
    progress = qml_item(root, "backtestProgressBanner")
    coverage = qml_item(root, "backtestCoverageWarningBanner")
    assert progress is not None
    assert coverage is not None

    vm.set_data_coverage(False, "Thiếu nến từ 2026-01-01 00:00 UTC.")
    vm.set_needs_data_sync(True)
    vm.set_sync_progress(45.0, "Đang đồng bộ nến: 45/100 (45%)")
    vm.set_ui_mode("SYNCING")

    qtbot.waitUntil(
        lambda: (
            progress.property("visible") is True
            and coverage.property("visible") is True
        ),
        timeout=2000,
    )


def test_dynamic_banners_do_not_trigger_qml_binding_or_render_frame_warnings(
    view, qapp
):
    from PySide6.QtCore import qInstallMessageHandler

    _v, vm = view
    messages: list[str] = []
    previous_handler = qInstallMessageHandler(
        lambda _type, _context, message: messages.append(message)
    )
    try:
        vm.set_data_coverage(False, "Thiếu nến")
        vm.set_needs_data_sync(True)
        vm.set_sync_progress(50.0, "Đang đồng bộ")
        vm.set_ui_mode("SYNCING")
        qapp.processEvents()
        vm.set_ui_mode("ERROR")
        qapp.processEvents()
    finally:
        qInstallMessageHandler(previous_handler)

    forbidden = ("Binding loop", "QQuickRenderControl")
    assert not [message for message in messages if message.startswith(forbidden)]


def test_trade_log_pane_never_shrinks_below_its_usable_minimum(view, qtbot):
    """The splitter must never be able to squeeze the Trade Logs pane below
    `minimumUsableHeight` (BackTestTradeLogs.qml) — BUG-004's screenshot is
    exactly what "squeezed below" looks like: header/tabs/pagination all
    rendered, table body empty. `setSizes([600, 200])` is only a starting
    hint; `setMinimumHeight()` is what actually prevents this."""
    v, _vm = view
    root = v.bottom_widget.rootObject()

    qtbot.waitUntil(
        lambda: v.bottom_widget.height() >= int(root.property("minimumUsableHeight")),
        timeout=2000,
    )


def test_overlay_host_covers_the_full_hybrid_backtest_view(view, qtbot):
    """BOT-087: the overlay must use the Backtest view's full bounds, not
    the top toolbar QQuickWidget's much smaller bounds.  Popup content moves
    into this host in BOT-088; this guard makes the geometry contract
    executable before that migration starts."""
    v, _vm = view

    qtbot.waitUntil(
        lambda: v.overlay_host.overlay_size == (v.width(), v.height()),
        timeout=2000,
    )

    assert v.overlay_host.quick_widget.parentWidget() is v
    assert v.overlay_host.is_click_through is True


def test_trade_log_rows_are_visible_by_default(view, qtbot, qml_item):
    """Regression guard for the exact failure mode in BUG-004/BOT-090: a
    75-trade result page (`PAGE_SIZE=20` rows) rendered with zero rows
    actually visible, even though the ListView had all 20 in its model —
    the pane itself was too short for even one. Waits for the 5th row
    (`minVisibleRows` in BackTestTradeLogs.qml) to be geometrically inside
    the widget's bounds, same `mapToItem` technique BOT-089 needed for the
    stat cards — a row's local `y` alone can't distinguish "positioned
    correctly" from "positioned past the visible edge"."""
    v, vm = view
    vm.set_trade_log_page_state(_trade_log_rows(20), 75, 4)

    def fifth_row_is_fully_visible() -> bool:
        root = v.bottom_widget.rootObject()
        row = qml_item(root, "rowTradeLog_4")  # 0-based -> the 5th row
        if row is None:
            return False
        absolute_y = row.mapToItem(root, 0, 0).y()
        row_bottom = absolute_y + row.property("height")
        return row_bottom <= v.bottom_widget.height()

    qtbot.waitUntil(fifth_row_is_fully_visible, timeout=2000)
