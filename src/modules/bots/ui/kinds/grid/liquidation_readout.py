"""`EPIC-043E` — the Liquidation row of a Futures Grid's editor: one line per side, each in the
tone the guard's own severity gives it.

@details A Neutral plan shows a Long and a Short line, and the two can differ (one refused, one
fine), so each side is its own label: one tone over both would paint the fine side as the refused
one. The words stay what `grid_liquidation.py` wrote ("Blocks Start:", "Advice:"); the tone only
adds to them. Until the guard has judged a plan there is one plain line saying so.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_liquidation import (
    NOT_ESTIMATED,
    LiquidationLine,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.verdict_tone import verdict_tone
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import Tone
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label
from Sagittarius_Elite_Warrior.src.support.ui_kit.tone_label import paint_label_tone


class LiquidationReadout(QWidget):  # base-exempt: a read-only row of labels
    """@brief The editor's liquidation lines, one label each."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("lblGridLiquidation")
        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._labels: list[QLabel] = []
        self.show_unjudged()

    def show_unjudged(self) -> None:
        """No verdict yet: one plain line saying so."""
        self._set_lines([(NOT_ESTIMATED, Tone.NEUTRAL)])

    def show_lines(self, lines: Sequence[LiquidationLine]) -> None:
        """One line per side the guard judged; the unjudged line when it judged none."""
        if not lines:
            self.show_unjudged()
            return
        self._set_lines([(line.text, verdict_tone(line.severity)) for line in lines])

    def text(self) -> str:
        """What the row says, a line per side."""
        return "\n".join(label.text() for label in self._labels)

    def label_of(self, position: int) -> QLabel:
        """The label of the `position`th line, for a test or a layout check."""
        return self._labels[position]

    def _set_lines(self, lines: Sequence[tuple[str, Tone]]) -> None:
        while len(self._labels) > len(lines):
            label = self._labels.pop()
            self._column.removeWidget(label)
            label.deleteLater()
        while len(self._labels) < len(lines):
            label = plain_label()
            label.setWordWrap(True)
            label.setObjectName(f"lblGridLiquidation::{len(self._labels)}")
            self._column.addWidget(label)
            self._labels.append(label)
        for label, (text, tone) in zip(self._labels, lines, strict=True):
            label.setText(text)
            paint_label_tone(label, tone)
