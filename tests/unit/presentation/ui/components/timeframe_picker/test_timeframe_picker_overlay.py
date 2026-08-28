"""Tests for the shared TimeframePickerOverlay widget."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.components.timeframe_picker import (
    TimeframePickerOverlay,
)

_ALL = [member.value for member in TimeFrame]


class _Source:
    """Stands in for a screen: owns what the dialog reads, so the tests can
    change it between opens the way a real screen does."""

    def __init__(self, current="1m", options=None):
        self.options = list(_ALL if options is None else options)
        self.current = current

    def build(self, qapp):
        dialog = TimeframePickerOverlay(
            get_options=lambda: self.options,
            get_current=lambda: self.current,
        )
        dialog.show()
        qapp.processEvents()
        return dialog


def _codes(dialog):
    return [card.option.code for card in dialog._cards]


def test_opening_renders_every_offered_timeframe(qapp):
    dialog = _Source().build(qapp)

    assert sorted(_codes(dialog)) == sorted(_ALL)
    assert len(_codes(dialog)) == 16, "the old picker offered 5"
    dialog.close()


def test_cards_are_grouped_shortest_first(qapp):
    dialog = _Source().build(qapp)

    assert _codes(dialog)[0] == "1s"
    assert _codes(dialog)[-1] == "1M"
    dialog.close()


def test_the_current_timeframe_is_marked(qapp):
    dialog = _Source(current="4h").build(qapp)

    current = [card for card in dialog._cards if card.selected]
    assert [card.option.code for card in current] == ["4h"]
    assert "4h" in dialog._current_label.text()
    dialog.close()


def test_choosing_emits_the_code_and_closes(qapp):
    dialog = _Source().build(qapp)
    chosen: list[str] = []
    dialog.timeframe_chosen.connect(chosen.append)

    card = next(c for c in dialog._cards if c.option.code == "12h")
    card.clicked.emit()
    qapp.processEvents()

    assert chosen == ["12h"]
    assert not dialog.isVisible()


def test_a_screen_that_offers_no_timeframes_says_so(qapp):
    dialog = _Source(options=[]).build(qapp)

    assert dialog._status_label.isVisible()
    assert not dialog._scroll.isVisible()
    dialog.close()


def test_the_high_resolution_warning_appears_only_when_1s_is_offered(qapp):
    dialog = _Source().build(qapp)
    assert dialog._warning_label.isVisible()
    dialog.close()

    dialog = _Source(options=["1m", "1h"]).build(qapp)
    assert not dialog._warning_label.isVisible()
    dialog.close()


def test_reopening_rereads_the_options_and_the_current_choice(qapp):
    """The dialog is built once and reused, so nothing may be captured at
    construction."""
    source = _Source()
    dialog = source.build(qapp)
    assert len(dialog._cards) == 16
    dialog.close()

    source.options = ["1m", "5m"]
    source.current = "5m"
    dialog.show()
    qapp.processEvents()

    assert _codes(dialog) == ["1m", "5m"], "old cards must not survive a refresh"
    assert "5m" in dialog._current_label.text()
    dialog.close()


def test_arrow_keys_move_a_highlight_and_enter_chooses_it(qapp):
    dialog = _Source().build(qapp)
    chosen: list[str] = []
    dialog.timeframe_chosen.connect(chosen.append)

    QTest.keyClick(dialog, Qt.Key.Key_Down)
    QTest.keyClick(dialog, Qt.Key.Key_Down)
    qapp.processEvents()
    assert dialog._cards[1].selected is True

    QTest.keyClick(dialog, Qt.Key.Key_Return)
    qapp.processEvents()

    assert chosen == [_codes(dialog)[1]]
