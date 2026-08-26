"""Item delegate that lets a list row render as a real widget.

Its own module because it has two unrelated consumers -- the Data
Management view's status list and the K-line inspector's table."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QStyledItemDelegate,
)


class RowWidgetDelegate(QStyledItemDelegate):
    """Sizes a `QListView` item to the widget actually placed in it.

    `setIndexWidget()` does not tell the list how tall its widget is — the
    item keeps the delegate's default height, which is one line of text.
    Both of this screen's tables have been clipped to 14px since it was
    ported: enough for the labels, not for a row's action buttons, which is
    why those rendered as empty outlines with their text cut off
    (`BUG-057`).

    Reading the widget's own `sizeHint()` rather than naming a height keeps
    the two from drifting when a row gains a taller control.
    """

    def sizeHint(self, option, index):
        hint = super().sizeHint(option, index)
        view = self.parent()
        widget = view.indexWidget(index) if view is not None else None
        if widget is None:
            return hint
        hint.setHeight(max(hint.height(), widget.sizeHint().height()))
        return hint
