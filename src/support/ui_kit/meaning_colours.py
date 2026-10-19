"""The app's one meaning table (`ui-presentation-rule.md` §1).

Colour appears only where it carries meaning, and never alone: the sign or the
word stays in the text beside it. A figure is painted by its `Tone`, the
verdict a rule gave it; a surface asks `tone_colour` and leaves the platform's
text colour alone when the answer is `None`.

Without a palette, profit and loss are the chart's bull and bear colours
(`support/charting/chart_card/theme.py`), the one place their values are
written, so a table's profit and a chart's up-candle cannot drift apart.

With a palette (`EPIC-033U`) the colour is one that reads as text on that
palette's `Base`: a dark variant on a light base, a light one on a dark base,
each a named colour (never a hex) with at least `MIN_TEXT_CONTRAST` against
the extreme of its scheme. In Windows High Contrast no colour is returned, so
the platform's own text colours stand (`ui-presentation-rule.md` §1).

Capability: Colour something by meaning (good, bad, warning), never a hex
    Also: colour, red green, tone, palette, stylesheet
    Use: Tone, tone_colour
    User: src/modules/backtesting/ui/backtest_stat_row.py
    Status: stable
"""

from __future__ import annotations

import ctypes
import sys
from enum import Enum, auto

from PySide6.QtGui import QColor, QPalette
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)


class Tone(Enum):
    """The verdict a figure carries."""

    NEUTRAL = auto()
    POSITIVE = auto()
    NEGATIVE = auto()
    #: Needs a look but is not a loss: a paused or recovering bot.
    CAUTION = auto()


PROFIT_COLOUR = QColor(BULL_COLOR)
LOSS_COLOUR = QColor(BEAR_COLOR)

_TONE_COLOURS = {Tone.POSITIVE: PROFIT_COLOUR, Tone.NEGATIVE: LOSS_COLOUR}


#: WCAG 2.x success criterion 1.4.3: the contrast text needs against its background.
MIN_TEXT_CONTRAST = 4.5

#: The named colours of each tone on a light base and on a dark base.
_LIGHT_BASE_COLOURS = {
    Tone.POSITIVE: "darkgreen",
    Tone.NEGATIVE: "firebrick",
    Tone.CAUTION: "saddlebrown",
}
_DARK_BASE_COLOURS = {
    Tone.POSITIVE: "lightgreen",
    Tone.NEGATIVE: "lightcoral",
    Tone.CAUTION: "darkorange",
}

_SPI_GETHIGHCONTRAST = 0x0042
_HCF_HIGHCONTRASTON = 0x1


class _HighContrast(ctypes.Structure):
    _fields_ = (
        ("cbSize", ctypes.c_uint),
        ("dwFlags", ctypes.c_ulong),
        ("lpszDefaultScheme", ctypes.c_wchar_p),
    )


def is_high_contrast() -> bool:
    """Whether Windows High Contrast is on. Qt 6.11 has no query for it; other
    platforms say no, and their dark mode is the palette's own."""
    if sys.platform != "win32":
        return False
    info = _HighContrast(ctypes.sizeof(_HighContrast), 0, None)
    ok = ctypes.windll.user32.SystemParametersInfoW(  # type: ignore[attr-defined,unused-ignore]
        _SPI_GETHIGHCONTRAST, info.cbSize, ctypes.byref(info), 0
    )
    return bool(ok) and bool(info.dwFlags & _HCF_HIGHCONTRASTON)


def tone_colour(tone: Tone, palette: QPalette | None = None) -> QColor | None:
    """The colour a tone reads, or `None` for no verdict (leave the palette's
    text colour alone).

    Given a palette, the colour that reads on its `Base`, or `None` in
    High Contrast; without one, the chart's bull and bear (the backtest's
    colours before `EPIC-033U`).
    """
    if palette is None:
        colour = _TONE_COLOURS.get(tone)
        return None if colour is None else QColor(colour)
    if is_high_contrast():
        return None
    dark = palette.color(QPalette.ColorRole.Base).lightness() < _MIDDLE_LIGHTNESS
    name = (_DARK_BASE_COLOURS if dark else _LIGHT_BASE_COLOURS).get(tone)
    return None if name is None else QColor(name)


_MIDDLE_LIGHTNESS = 128
