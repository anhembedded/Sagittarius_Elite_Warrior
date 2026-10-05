"""`ChartChrome` — the colours of a chart's chrome, read from `QPalette` roles.

Chrome is what every chart has whatever it shows: the plot background, the
axes and their tick text, the grid, the crosshair and its axis tags. Since
`EPIC-033G` it takes the platform's colours (`ui-presentation-rule.md` §1:
colour only where it carries meaning), so the chart follows the system's light,
dark or high-contrast scheme like every stock control around it. What a colour
*means* — a candle that closed up, a stop-loss line — stays in `theme.py`, the
one named table of meaning colours.

| Chrome | Role | Why that role |
| :--- | :--- | :--- |
| background | `Base` | the background of a view that shows data (a table, an editor) |
| foreground | `Text` | text drawn on `Base`; axes and tick labels |
| grid | `Text`, faint | pyqtgraph draws the grid with the axis pen at an alpha |
| crosshair | `PlaceholderText` | secondary text on `Base`: visible, never louder than data |
| tag fill / tag text | `ToolTipBase` / `ToolTipText` | a small label over content is what a tooltip is |
| uncovered | `Window` | where a pan preview has no pixels: outside the data, so the backdrop, never mistaken for an empty plot |
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QWidget

#: How strongly pyqtgraph draws the grid over the axis pen (0–1).
GRID_ALPHA = 0.2


@dataclass(frozen=True)
class ChartChrome:
    """The chrome colours of one palette."""

    background: QColor
    foreground: QColor
    crosshair: QColor
    tag_fill: QColor
    tag_text: QColor
    uncovered: QColor

    @classmethod
    def from_palette(cls, palette: QPalette) -> ChartChrome:
        role = QPalette.ColorRole
        return cls(
            background=palette.color(role.Base),
            foreground=palette.color(role.Text),
            crosshair=palette.color(role.PlaceholderText),
            tag_fill=palette.color(role.ToolTipBase),
            tag_text=palette.color(role.ToolTipText),
            uncovered=palette.color(role.Window),
        )


class PaletteChangeWatcher(QObject):
    """Calls back with the new chrome when `widget`'s palette changes.

    A system scheme switch reaches every widget as `QEvent.PaletteChange`, so
    the chart repaints in the new colours without a restart.
    """

    def __init__(
        self, widget: QWidget, on_change: Callable[[ChartChrome], None]
    ) -> None:
        super().__init__(widget)
        self._widget = widget
        self._on_change = on_change
        widget.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self._widget and event.type() == QEvent.Type.PaletteChange:
            self._on_change(ChartChrome.from_palette(self._widget.palette()))
        return False
