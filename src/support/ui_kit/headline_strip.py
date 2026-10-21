"""`EPIC-043D` — a row of the few figures a screen is read for, set larger than the detail.

A trading screen has a handful of numbers the person looks at first (what the account is worth,
how the open positions are doing, how far the nearest is from liquidation). They sit in one row
above the detail, each a small caption over its figure. The figure is larger and bold, both
derived from the platform's own font (`ui-presentation-rule.md` §1: a widget may derive size or
weight, never a family), and a figure whose digits align is in the platform's fixed-pitch font,
decided by its kind (`kind_font`). The strip writes nothing itself: it is given each figure's text,
already written by the application's formatter, and the tone the meaning table gave it
(`paint_label_tone`), so the colour is never the only signal.

Capability: A row of headline figures, larger than the detail, each with a caption and a tone
    Also: key figures, summary row, kpi, big numbers, headline numbers, equity row
    Use: HeadlineStrip, HeadlineFigure
    User: src/modules/trading/ui/desk/desk_screen/desk_view.py
    Status: stable

While the figures can no longer be trusted the strip says "Out of date" in words, as the panel they
repeat does, and keeps them: they are the last ones read. It says no more: the reason is the
panel's, told once, and a short fixed word cannot widen the row past the window.

Extension cases: a figure that is not a number (a state) is one more `HeadlineFigure` with a
`ColumnKind.TEXT`; another screen's headline is one more caller of `show_figures`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.kind_font import kind_font
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import Tone
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label
from Sagittarius_Elite_Warrior.src.support.ui_kit.tone_label import paint_label_tone
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind

#: What the strip says while its figures are the last ones read; the reason is the panel's.
STALE_TEXT: Final = "Out of date"

#: How much larger than the detail's text a headline figure is set.
HEADLINE_SCALE: Final = 1.5


@dataclass(frozen=True)
class HeadlineFigure:
    """One headline figure: what it is, how it reads, and what it means."""

    key: str
    caption: str
    #: The figure as the application's formatter wrote it.
    text: str
    #: The meaning table's verdict on it; `NEUTRAL` paints nothing.
    tone: Tone = Tone.NEUTRAL
    #: Decides the font: a kind whose digits align takes the platform's fixed-pitch font.
    kind: ColumnKind = field(default=ColumnKind.TEXT)


def _headline_font(base: QFont, kind: ColumnKind) -> QFont:
    """`base`, or the kind's own font, larger and bold; the family is the platform's either way."""
    font = QFont(kind_font(kind) or base)
    size = font.pointSizeF()
    if size > 0:
        font.setPointSizeF(size * HEADLINE_SCALE)
    font.setBold(True)
    return font


class _Cell(QWidget):  # base-exempt: a part of the strip, not a surface
    """A caption over a figure."""

    def __init__(self, key: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName(f"headline::{key}")
        self.caption: QLabel = plain_label()
        self.caption.setObjectName(f"headline::{key}::caption")
        self.value: QLabel = plain_label()
        self.value.setObjectName(f"headline::{key}::value")
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(self.caption)
        column.addWidget(self.value)

    def show_figure(self, figure: HeadlineFigure) -> None:
        self.caption.setText(figure.caption)
        self.value.setText(figure.text)
        self.value.setFont(_headline_font(self.caption.font(), figure.kind))
        paint_label_tone(self.value, figure.tone)


class HeadlineStrip(QWidget):  # base-exempt: a row of read-only labels
    """@brief The figures of a screen's headline, left to right."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("headlineStrip")
        self._cells: dict[str, _Cell] = {}
        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.addStretch(1)
        self._stale = plain_label()
        self._stale.setObjectName("headline::stale")
        self._stale.hide()
        self._row.addWidget(self._stale)
        self.hide()

    @property
    def keys(self) -> tuple[str, ...]:
        """The figures shown, in order."""
        return tuple(self._cells)

    def show_figures(self, figures: Sequence[HeadlineFigure]) -> None:
        """Shows exactly `figures`, in order; none hides the strip."""
        wanted = tuple(figure.key for figure in figures)
        if wanted != self.keys:
            self._rebuild(wanted)
        for figure in figures:
            self._cells[figure.key].show_figure(figure)
        self.setVisible(bool(figures))

    def mark_stale(self) -> None:
        """Says in words that the figures shown are the last ones read."""
        self._stale.setText(STALE_TEXT)
        self._stale.show()

    def clear_stale(self) -> None:
        self._stale.clear()
        self._stale.hide()

    @property
    def stale_text(self) -> str:
        return "" if self._stale.isHidden() else self._stale.text()

    def clear(self) -> None:
        self.show_figures(())

    def text_of(self, key: str) -> str | None:
        """The text shown for the figure `key`, or `None` when it is not shown."""
        cell = self._cells.get(key)
        return None if cell is None else cell.value.text()

    def cell_value(self, key: str) -> QLabel | None:
        """The label that carries the figure `key`, for a test or a layout check."""
        cell = self._cells.get(key)
        return None if cell is None else cell.value

    def _rebuild(self, wanted: tuple[str, ...]) -> None:
        for cell in self._cells.values():
            self._row.removeWidget(cell)
            cell.deleteLater()
        self._cells = {key: _Cell(key, self) for key in wanted}
        for position, cell in enumerate(self._cells.values()):
            self._row.insertWidget(position, cell)
