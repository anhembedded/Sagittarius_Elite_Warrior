"""`EPIC-043C` — a label whose text takes a tone's colour on the application's palette.

A figure in a label (a read-out's PnL, a banner's sentence) is toned the way a table cell is:
by the meaning table's colour for its `Tone`, asked of the palette at the time and again when the
palette changes, so a switch of the colour scheme repaints it. The text carries the meaning in
words, a sign or an arrow; the colour only adds to it, and in High Contrast there is none
(`meaning_colours.py`). No style sheet and no colour is written: the label's `WindowText` role is
set, from the table, on the label's own palette: on every role a label draws its text with,
because a label inside a toolbar draws with `ButtonText`, not `WindowText`.

Capability: Colour a label's text by meaning (profit, loss, warning), following the colour scheme
    Also: tone, colour a label, red green text, read-out colour, label palette
    Use: paint_label_tone
    User: src/support/ui_kit/readout_slot.py
    Status: stable
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QGuiApplication, QPalette
from PySide6.QtWidgets import QLabel
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import (
    Tone,
    tone_colour,
)

_FOLLOWER_NAME = "toneFollower"
#: The roles a label's text is drawn with: its own by default, a toolbar's or a button row's
#: when the label stands in one (`QWidget.foregroundRole` follows the parent).
_TEXT_ROLES = (
    QPalette.ColorRole.WindowText,
    QPalette.ColorRole.ButtonText,
    QPalette.ColorRole.Text,
)


class _ToneFollower(QObject):
    """Holds a label's tone and paints it again when the application's palette changes."""

    def __init__(self, label: QLabel) -> None:
        super().__init__(label)
        self.setObjectName(_FOLLOWER_NAME)
        self._label = label
        self._tone = Tone.NEUTRAL
        label.installEventFilter(self)

    def show(self, tone: Tone) -> None:
        self._tone = tone
        self._paint()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if (
            watched is self._label
            and event.type() == QEvent.Type.ApplicationPaletteChange
        ):
            self._paint()
        return False

    def _paint(self) -> None:
        colour = tone_colour(self._tone, QGuiApplication.palette())
        if colour is None:
            # Back to the platform's own colour: a label that had a tone and has none now.
            self._label.setPalette(QPalette())
            return
        palette = QPalette(self._label.palette())
        for role in _TEXT_ROLES:
            palette.setColor(role, colour)
        self._label.setPalette(palette)


def paint_label_tone(label: QLabel, tone: Tone) -> None:
    """Shows `label`'s text in `tone`'s colour (none for `NEUTRAL`), from now on and after
    every change of the application's palette."""
    follower = label.findChild(_ToneFollower, _FOLLOWER_NAME)
    if follower is None:
        if tone is Tone.NEUTRAL:
            return
        follower = _ToneFollower(label)
    follower.show(tone)
