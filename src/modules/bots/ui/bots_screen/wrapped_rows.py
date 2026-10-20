"""`BOT-206`, `BOT-209` — the height of a wrapped row in an item view.

`QTreeView` paints wrapped text but sizes a row from one line, so a view that wraps asks each row's
height of its text at the column's width and gives it as the row's `SizeHintRole`. Both Plan-dock
lists (the property table and the checks) ask it here.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QAbstractItemView, QStyle


def wrapped_line_count(font: QFont, text: str, width: int) -> int:
    """How many lines `text` takes in `width` pixels."""
    metrics = QFontMetrics(font)
    wrapped = metrics.boundingRect(
        QRect(0, 0, width, 0), Qt.TextFlag.TextWordWrap, text
    )
    return max(round(wrapped.height() / metrics.lineSpacing()), 1)


def wrapped_row_size(view: QAbstractItemView, lines: int) -> QSize:
    """The style's height of one line, and a line's spacing for each line more."""
    metrics = view.fontMetrics()
    margin = view.style().pixelMetric(QStyle.PixelMetric.PM_FocusFrameVMargin) + 1
    return QSize(0, metrics.height() + 2 * margin + metrics.lineSpacing() * (lines - 1))
