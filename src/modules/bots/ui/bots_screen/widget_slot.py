"""One widget at a time in a layout: the bots mode's slots for what the
presenter hands over (the kind's editor, the chart, the kind's backtest)."""

from __future__ import annotations

from PySide6.QtWidgets import QLayout, QWidget


def replace_in(slot: QLayout, widget: QWidget | None) -> None:
    """Takes every widget out of `slot`, then puts `widget` in, if any. The
    widget taken out is unparented, not deleted: its owner decides that."""
    while slot.count():
        item = slot.takeAt(0)
        old = item.widget() if item is not None else None
        if old is not None:
            old.setParent(None)
    if widget is not None:
        slot.addWidget(widget)
