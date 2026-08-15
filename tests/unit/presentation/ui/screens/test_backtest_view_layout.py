"""Tests for BackTestView's top-panel sizing (BOT-089).

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
    vm.set_stat_cards(_stat_cards(4), [])
    qtbot.waitUntil(
        lambda: qml_item(v.top_widget.rootObject(), "cardMetric_0") is not None,
        timeout=2000,
    )
    qtbot.wait(100)  # let the cards row's own height settle before the baseline read
    height_before = v.top_widget.height()

    vm.set_result_warning_text("⚠ Phí giao dịch chiếm phần lớn kết quả.")
    qtbot.wait(200)  # let any (unexpected) pending layout settle before asserting

    assert v.top_widget.height() == height_before
