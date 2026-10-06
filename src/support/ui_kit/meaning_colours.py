"""The app's one meaning table (`ui-presentation-rule.md` §1).

Colour appears only where it carries meaning, and never alone: the sign or the
word stays in the text beside it. A figure is painted by its `Tone`, the
verdict a rule gave it; a surface asks `tone_colour` and leaves the platform's
text colour alone when the answer is `None`.

Profit and loss are the chart's bull and bear colours
(`support/charting/chart_card/theme.py`), the one place their values are
written, so a table's profit and a chart's up-candle cannot drift apart.
"""

from __future__ import annotations

from enum import Enum, auto

from PySide6.QtGui import QColor
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)


class Tone(Enum):
    """The verdict a figure carries."""

    NEUTRAL = auto()
    POSITIVE = auto()
    NEGATIVE = auto()


PROFIT_COLOUR = QColor(BULL_COLOR)
LOSS_COLOUR = QColor(BEAR_COLOR)

_TONE_COLOURS = {Tone.POSITIVE: PROFIT_COLOUR, Tone.NEGATIVE: LOSS_COLOUR}


def tone_colour(tone: Tone) -> QColor | None:
    """The colour a tone reads, or `None` for no verdict (leave the palette's
    text colour alone)."""
    colour = _TONE_COLOURS.get(tone)
    return None if colour is None else QColor(colour)
