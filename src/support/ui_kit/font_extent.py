"""A size counted in the system font's characters and lines, never in pixels."""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QWidget


def font_extent(widget: QWidget, base: QSize, chars: int, lines: int) -> QSize:
    """`base` grown to at least `chars` average characters wide and `lines` text
    lines tall in `widget`'s font, so a dialog follows the user's font size."""
    metrics = widget.fontMetrics()
    return QSize(
        max(base.width(), metrics.averageCharWidth() * chars),
        max(base.height(), metrics.lineSpacing() * lines),
    )
