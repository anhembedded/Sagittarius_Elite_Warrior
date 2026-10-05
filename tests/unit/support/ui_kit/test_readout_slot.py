"""`ReadoutSlot`: a read-out whose rows can change (`EPIC-033N`)."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QLabel
from Sagittarius_Elite_Warrior.src.support.ui_kit.readout_slot import (
    Readout,
    ReadoutSlot,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    ReadoutForm,
)

_USDT = (
    ColumnSpec("available", "Available (USDT)", ColumnKind.MONEY),
    ColumnSpec("price", "Price", ColumnKind.PRICE),
)
_USD = (ColumnSpec("available", "Available (USD)", ColumnKind.MONEY),)


def test_an_empty_slot_shows_no_rows(qapp):
    slot = ReadoutSlot()

    assert slot.keys == ()
    assert slot.value_text("available") is None
    assert slot.findChildren(ReadoutForm) == []


def test_values_are_written_by_kind(qapp):
    slot = ReadoutSlot()

    slot.show_readout(Readout(_USDT, {"available": 1234.567, "price": 0.00001234}))

    assert slot.value_text("available") == "1,234.57"
    assert slot.value_text("price") == "0.00001234"
    assert slot.value_text("missing") is None


def test_new_values_for_the_same_rows_keep_the_form(qapp):
    slot = ReadoutSlot()
    slot.show_readout(Readout(_USDT, {"available": 1.0}))
    form = slot.findChild(ReadoutForm)

    slot.show_readout(Readout(_USDT, {"available": 2.0}))

    assert slot.findChild(ReadoutForm) is form
    assert slot.value_text("available") == "2.00"


def test_new_rows_build_a_new_form(qapp):
    slot = ReadoutSlot()
    slot.show_readout(Readout(_USDT, {"available": 1.0}))

    slot.show_readout(Readout(_USD, {"available": 3.0}))

    assert slot.keys == ("available",)
    assert slot.value_text("available") == "3.00"
    # The old form is deleted once the event loop runs; one form remains,
    # titled for the new rows.
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    (form,) = slot.findChildren(ReadoutForm)
    titles = {label.text() for label in form.findChildren(QLabel)}
    assert "Available (USD)" in titles
    assert "Available (USDT)" not in titles


def test_clear_removes_the_rows(qapp):
    slot = ReadoutSlot()
    slot.show_readout(Readout(_USDT, {"available": 1.0}))

    slot.clear()

    assert slot.keys == ()
    assert slot.value_text("available") is None
