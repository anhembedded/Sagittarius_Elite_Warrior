"""Tests for the shared `MarketPickerDialog` widget.

Restated in `EPIC-025` PR 4.3e, when the body moved from `SelectList.qml` onto
`kit.PickerOverlay`. All four promises are the same sentences; only the way a
test reaches a row changed — `SelectableCard`s in a grid layout rather than
named items inside a `QQuickWidget`'s scene.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QLabel
from Sagittarius_Elite_Warrior.src.domain.value_objects.market_type import MarketType
from Sagittarius_Elite_Warrior.src.presentation.ui.components.market_picker import (
    MarketPickerDialog,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import SelectableCard


class _Source:
    """Stands in for a screen: owns what the dialog reads, so the tests can
    change it between opens the way a real screen does — same shape
    `test_timeframe_picker_overlay.py`'s `_Source` uses."""

    def __init__(self, current: str = MarketType.SPOT.value) -> None:
        self.current = current

    def build(self, qapp) -> MarketPickerDialog:
        dialog = MarketPickerDialog(get_current=lambda: self.current)
        dialog.show()
        qapp.processEvents()
        return dialog


def _cards(dialog: MarketPickerDialog) -> list[SelectableCard]:
    found = []
    for index in range(dialog._grid.count()):
        entry = dialog._grid.itemAt(index)
        widget = None if entry is None else entry.widget()
        if isinstance(widget, SelectableCard):
            found.append(widget)
    return found


def _labels(dialog: MarketPickerDialog) -> list[str]:
    return [card.findChild(QLabel).text() for card in _cards(dialog)]


def _card_for(dialog: MarketPickerDialog, label: str) -> SelectableCard:
    return _cards(dialog)[_labels(dialog).index(label)]


def test_opening_renders_every_market(qapp):
    dialog = _Source().build(qapp)

    assert _labels(dialog) == ["Spot", "Futures (USD-M)", "Futures (COIN-M)"]
    dialog.close()


def test_the_current_market_is_marked_selected(qapp):
    dialog = _Source(current=MarketType.FUTURES_USD_M.value).build(qapp)

    assert _card_for(dialog, "Futures (USD-M)").selected is True
    assert _card_for(dialog, "Spot").selected is False
    dialog.close()


def test_choosing_emits_the_market_id_and_closes(qapp):
    dialog = _Source().build(qapp)
    chosen: list[str] = []
    dialog.chosen.connect(chosen.append)

    _card_for(dialog, "Futures (COIN-M)").clicked.emit()
    qapp.processEvents()

    assert chosen == [MarketType.FUTURES_COIN_M.value]
    assert not dialog.isVisible()


def test_reopening_rereads_the_current_choice(qapp):
    """The dialog is built once and reused, so nothing may be captured at
    construction — same contract `TimeframePickerDialog.open_dialog()`
    documents."""
    source = _Source(current=MarketType.SPOT.value)
    dialog = source.build(qapp)
    assert _card_for(dialog, "Spot").selected is True
    dialog.close()

    source.current = MarketType.FUTURES_USD_M.value
    dialog.show()
    qapp.processEvents()

    assert _card_for(dialog, "Futures (USD-M)").selected is True
    assert _card_for(dialog, "Spot").selected is False
    dialog.close()
