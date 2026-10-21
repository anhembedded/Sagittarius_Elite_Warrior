"""`EPIC-043C`: a read-out row says what it means and its value is painted in that tone."""

from __future__ import annotations

from PySide6.QtGui import QGuiApplication, QPalette
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import (
    Tone,
    tone_colour,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.readout_slot import (
    Readout,
    ReadoutSlot,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import signed_key
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind, ColumnSpec

_PNL = signed_key("pnl")
_SPECS = (
    ColumnSpec(_PNL, "PnL", ColumnKind.MONEY),
    ColumnSpec("fee", "Fee", ColumnKind.MONEY),
)
_TEXT = QPalette.ColorRole.WindowText


def _colour(slot: ReadoutSlot, key: str):
    label = slot.value_label(key)
    assert label is not None
    return label.palette().color(_TEXT)


def test_a_toned_row_takes_the_colour_and_says_its_direction_in_words(qtbot) -> None:
    slot = ReadoutSlot()
    qtbot.addWidget(slot)

    slot.show_readout(Readout(_SPECS, {_PNL: -5.0, "fee": 1.0}, {_PNL: Tone.NEGATIVE}))

    assert slot.value_text(_PNL) == "▼ -5.00"
    assert _colour(slot, _PNL) == tone_colour(Tone.NEGATIVE, QGuiApplication.palette())
    assert slot.value_text("fee") == "1.00"


def test_a_row_without_a_tone_keeps_the_platforms_colour(qtbot) -> None:
    slot = ReadoutSlot()
    qtbot.addWidget(slot)
    slot.show_readout(Readout(_SPECS, {_PNL: -5.0, "fee": 1.0}, {_PNL: Tone.NEGATIVE}))
    plain = _colour(slot, "fee")

    assert plain != _colour(slot, _PNL)
    assert plain == slot.palette().color(_TEXT)


def test_a_row_that_stops_being_a_loss_gets_its_colour_back(qtbot) -> None:
    slot = ReadoutSlot()
    qtbot.addWidget(slot)
    slot.show_readout(Readout(_SPECS, {_PNL: -5.0}, {_PNL: Tone.NEGATIVE}))

    slot.show_readout(Readout(_SPECS, {_PNL: 0.0}, {}))

    assert slot.value_text(_PNL) == "0.00"
    assert _colour(slot, _PNL) == slot.palette().color(_TEXT)
