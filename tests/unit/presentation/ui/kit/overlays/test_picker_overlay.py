"""Tests for `widgets.overlays.picker_overlay.PickerOverlay`."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    Overlay,
    PickerItem,
    PickerOverlay,
    SelectableCard,
)


def _cards(overlay: PickerOverlay) -> list[SelectableCard]:
    widgets = []
    for i in range(overlay._grid.count()):
        entry = overlay._grid.itemAt(i)
        widget = None if entry is None else entry.widget()
        if isinstance(widget, SelectableCard):
            widgets.append(widget)
    return widgets


def _labels(overlay: PickerOverlay) -> list[str]:
    from PySide6.QtWidgets import QLabel

    return [card.findChild(QLabel).text() for card in _cards(overlay)]


def test_constructs_as_a_modal_overlay(qtbot):
    overlay = PickerOverlay("CHỌN SYMBOL")
    qtbot.addWidget(overlay)

    assert isinstance(overlay, Overlay)
    assert overlay.isModal() is True
    assert overlay.selected is None


def test_rejects_a_column_count_below_one(qtbot):
    with pytest.raises(ValueError, match="columns must be >= 1"):
        PickerOverlay("Title", columns=0)


def test_set_items_renders_one_selectable_card_each(qtbot):
    overlay = PickerOverlay("CHỌN KHUNG THỜI GIAN")
    qtbot.addWidget(overlay)

    overlay.set_items([PickerItem("1m", "1m"), PickerItem("1h", "1h")])

    assert len(_cards(overlay)) == 2
    assert _labels(overlay) == ["1m", "1h"]


def test_set_items_replaces_rather_than_appends(qtbot):
    """The app hand-writes a drain-and-refill loop in eight places because
    its option lists arrive asynchronously and `showEvent` re-syncs. Calling
    twice must not stack."""
    overlay = PickerOverlay("Title")
    qtbot.addWidget(overlay)

    overlay.set_items([PickerItem("a", "A"), PickerItem("b", "B")])
    overlay.set_items([PickerItem("c", "C")])

    assert _labels(overlay) == ["C"]


def test_clicking_a_card_sets_selected_and_emits(qtbot):
    overlay = PickerOverlay("Title")
    qtbot.addWidget(overlay)
    overlay.set_items([PickerItem("btc", "BTCUSDT"), PickerItem("eth", "ETHUSDT")])

    with qtbot.waitSignal(overlay.selection_changed, timeout=1000) as blocker:
        _cards(overlay)[1].clicked.emit()

    assert blocker.args == ["eth"]
    assert overlay.selected == "eth"


def test_choosing_does_not_close_the_dialog(qtbot):
    """Deliberate: the app's time-range picker must stay open when "custom"
    is chosen so it can reveal its own fields. Closing is the consumer's
    call, not this base's."""
    overlay = PickerOverlay("Title")
    qtbot.addWidget(overlay)
    overlay.set_items([PickerItem("custom", "Tùy chỉnh")])

    _cards(overlay)[0].clicked.emit()

    assert overlay.result() == 0
    assert overlay.isVisible() is False  # never shown; also never accepted


def test_the_chosen_card_renders_as_selected(qtbot):
    overlay = PickerOverlay("Title")
    qtbot.addWidget(overlay)
    overlay.set_items([PickerItem("a", "A"), PickerItem("b", "B")])

    _cards(overlay)[1].clicked.emit()

    assert [card.selected for card in _cards(overlay)] == [False, True]


def test_selected_can_be_preset_by_the_consumer(qtbot):
    overlay = PickerOverlay("Title")
    qtbot.addWidget(overlay)
    overlay.set_items([PickerItem("a", "A"), PickerItem("b", "B")])

    overlay.selected = "a"

    assert [card.selected for card in _cards(overlay)] == [True, False]


def test_search_field_is_hidden_unless_searchable(qtbot):
    plain = PickerOverlay("Title")
    qtbot.addWidget(plain)
    plain.set_items([PickerItem("a", "A")])

    searchable = PickerOverlay("Title", searchable=True)
    qtbot.addWidget(searchable)
    searchable.set_items([PickerItem("a", "A")])

    assert plain._search_field.isVisibleTo(plain) is False
    assert searchable._search_field.isVisibleTo(searchable) is True


def test_search_filters_case_insensitively(qtbot):
    overlay = PickerOverlay("Title", searchable=True)
    qtbot.addWidget(overlay)
    overlay.set_items(
        [
            PickerItem("btc", "BTCUSDT"),
            PickerItem("eth", "ETHUSDT"),
            PickerItem("bnb", "BNBUSDT"),
        ]
    )

    overlay._search_field.setText("eth")

    assert _labels(overlay) == ["ETHUSDT"]


def test_filtering_does_not_discard_the_unmatched_items(qtbot):
    overlay = PickerOverlay("Title", searchable=True)
    qtbot.addWidget(overlay)
    overlay.set_items([PickerItem("btc", "BTCUSDT"), PickerItem("eth", "ETHUSDT")])

    overlay._search_field.setText("eth")
    overlay._search_field.setText("")

    assert _labels(overlay) == ["BTCUSDT", "ETHUSDT"]


def test_empty_state_replaces_the_list_and_the_search_field(qtbot):
    overlay = PickerOverlay(
        "Title", searchable=True, empty_text="Đang tải danh sách symbol từ sàn..."
    )
    qtbot.addWidget(overlay)

    assert overlay._empty_label.isVisibleTo(overlay) is True
    assert overlay._scroll.isVisibleTo(overlay) is False
    assert overlay._search_field.isVisibleTo(overlay) is False

    overlay.set_items([PickerItem("a", "A")])

    assert overlay._empty_label.isVisibleTo(overlay) is False
    assert overlay._scroll.isVisibleTo(overlay) is True


def test_list_shape_renders_a_subtitle(qtbot):
    overlay = PickerOverlay("CHỌN CHIẾN LƯỢC BOT")
    qtbot.addWidget(overlay)

    overlay.set_items([PickerItem("ema", "EMA Cross", "Mã: ema")])

    from PySide6.QtWidgets import QLabel

    texts = [label.text() for label in _cards(overlay)[0].findChildren(QLabel)]
    assert texts == ["EMA Cross", "Mã: ema"]


def test_grid_shape_drops_the_subtitle(qtbot):
    """A grid cell is one centred line; a subtitle would make that one cell
    taller than its neighbours."""
    overlay = PickerOverlay("CHỌN SYMBOL", columns=3)
    qtbot.addWidget(overlay)

    overlay.set_items([PickerItem("ema", "EMA Cross", "Mã: ema")])

    from PySide6.QtWidgets import QLabel

    texts = [label.text() for label in _cards(overlay)[0].findChildren(QLabel)]
    assert texts == ["EMA Cross"]


def test_grid_wraps_at_the_column_count(qtbot):
    overlay = PickerOverlay("Title", columns=3)
    qtbot.addWidget(overlay)

    overlay.set_items([PickerItem(str(i), str(i)) for i in range(5)])

    positions = [
        overlay._grid.getItemPosition(i)[:2] for i in range(overlay._grid.count())
    ]
    assert positions == [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1)]


def test_picker_has_no_footer_buttons(qtbot):
    """None of the app's six pickers has one — they are dismissed by
    choosing, or by the window's close control."""
    overlay = PickerOverlay("Title")
    qtbot.addWidget(overlay)

    from PySide6.QtWidgets import QPushButton

    assert overlay.findChildren(QPushButton) == []
