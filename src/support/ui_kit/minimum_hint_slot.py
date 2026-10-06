"""A panel's content that asks its dock area for no more than its minimum
(`EPIC-033I`).

`QMainWindow` gives each dock area the size hint of what it holds. A table's
or a chart's own hint runs to hundreds of pixels, so a bottom panel holding
one takes half the window from the mode's central widget. Wrapped in this
slot, the panel starts at its minimum and the central widget keeps the
larger share; the person still drags the panel taller.

The Bots mode's Backtest panel found this first (`_BacktestSlot`, PR #361);
it may use this class instead. Plausible extensions, each local: a slot that
asks for a fraction of the window (one method); a width-only variant for a
side panel (one class).
"""

from __future__ import annotations

from typing import override

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QVBoxLayout, QWidget


class MinimumHintSlot(QWidget):
    """Holds `content` and hints its minimum size as its preferred one."""

    def __init__(self, content: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(content)

    @override
    def sizeHint(self) -> QSize:
        return self.minimumSizeHint()
