"""One widget at a time in a layout: the bots mode's slots for what the
presenter hands over (the kind's editor, the chart, the kind's backtest).

@details A widget the slot gives up is never left parentless: a parentless widget is a window of its
own, and the show a layout queues for each widget it takes in (`QLayout.addChildWidget`) runs on the
event loop, so a widget swapped out again within one turn (two quick selections) would be shown as a
window at the screen's corner after it left (`BUG-242`). A widget leaves hidden by the owner's say
(`hide`, which that queued show respects) and:
· one that declared itself disposable (`WA_DeleteOnClose`: a note, an editor built for one selection)
  is closed, which deletes it;
· any other is kept, hidden, as a child of the slot's owner, until its owner brings it back or deletes
  it (a chart that survives a selection, a workbench per venue)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLayout, QWidget


def replace_in(slot: QLayout, widget: QWidget | None) -> None:
    """Takes every widget out of `slot`, then puts `widget` in, shown, if any."""
    owner = slot.parentWidget()
    while slot.count():
        item = slot.takeAt(0)
        old = item.widget() if item is not None else None
        if old is not None:
            _retire(old, owner)
    if widget is not None:
        slot.addWidget(widget)
        widget.show()


def _retire(old: QWidget, owner: QWidget | None) -> None:
    old.hide()
    if old.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose):
        old.close()
        return
    old.setParent(owner)
    old.hide()
