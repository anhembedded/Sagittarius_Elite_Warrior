"""The Backtest mode's primary performance figures, as a read-out —
`EPIC-025` PR 4.3g, `EPIC-033N`.

## What this replaces, and why it is not a card

`EPIC-006E` drew these as `MetricCard.qml`, `EPIC-007F` replaced that with the
QtWidgets `kit.StatCard`, and `EPIC-015` Phase 4 replaced *that* with
`StatCardRow.qml` (a `Repeater` of `StatCard.qml`). All three were cards: a
titled box with a border and a background. HLD §11.3 retires the card outright —
the user's judgement, *"các card cũ cũng rất là tệ"* — and offers a **read-only
summary** in its place. That is what this is: label and figure, one row each,
no chrome of its own.

`EPIC-033N` then made it the read-out every other panel is: a `ReadoutSlot`
(`readout_slot.py`) over the Engine's `ReadoutForm`, the figures arriving raw
with their kind and written by `AppValueFormatter`, so a profit reads as it does
in the trade log. It was a grid of hand-built tiles whose text came formatted
from the Presenter's helpers.

Its own file rather than another method on `BackTestTopPanel`, which is already
over `architecture-rule` §5's 400-line ceiling; adding to it would make a
pre-existing violation worse.

## Colour

ADR D21 leaves colour *only* where it carries meaning, and only through a
`QPalette` role or a per-widget property. A profit figure is such a case: green
for gain and red for loss is a convention of the domain this app is in, not
decoration this screen invented, so the tone survives — written onto the one
label that carries the figure, in the colour `readout_table` gives a verdict (the
one the Trades table uses). Nothing else here is coloured, no stylesheet is set:
every other pixel is the platform's theme.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.performance_metrics_view import (
    badge_key,
    cards_readout,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import (
    Tone,
    tone_colour,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.readout_slot import ReadoutSlot

_KEY_KEY = "key"
_VALUE_TONE_KEY = "valueTone"
_BADGE_TONE_KEY = "badgeTone"


def _tone_colour(value: object) -> QColor | None:
    """The colour a tone carries, or `None` for "no verdict".

    `None` leaves the label on the platform's own text colour, which is what
    `Tone.NEUTRAL`, a missing key and a value that is not a `Tone` at all all
    mean — the same fallback every card dict upstream already assumes.
    """
    return tone_colour(value) if isinstance(value, Tone) else None


class BacktestStatRow(QWidget):  # base-exempt: a container, not a surface
    """
    @brief The run's primary performance figures, rewritten when its numbers
    change.

    @details Callback-constructed, like every widget this rollout has moved:
    it reads `primaryStatCards` live, and its caller decides *when* to
    `refresh()` — `BackTestTopPanel._sync_stat_cards()` calls it once per
    `statCardsChanged`. This class subscribes to nothing, so exactly one place
    decides the cadence.
    """

    def __init__(
        self,
        get_cards: Callable[[], Sequence[Mapping[str, object]]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("statCardRowWidget")
        self._get_cards = get_cards
        self._readout = ReadoutSlot()
        self._readout.setObjectName("backtestFigures")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._readout)
        self.refresh()

    @property
    def readout(self) -> ReadoutSlot:
        """The figures' read-out, for a caller that asks what a row shows."""
        return self._readout

    def refresh(self) -> None:
        """Re-pulls `get_cards()` and shows it."""
        cards = self._get_cards()
        if not cards:
            self._readout.clear()
            return
        self._readout.show_readout(cards_readout(cards))
        for card in cards:
            key = str(card[_KEY_KEY])
            self._paint(self._readout.value_label(key), card.get(_VALUE_TONE_KEY))
            self._paint(
                self._readout.value_label(badge_key(key)), card.get(_BADGE_TONE_KEY)
            )

    @staticmethod
    def _paint(label: QLabel | None, tone: object) -> None:
        """Writes a tone onto one label, or leaves the theme's colour alone —
        the form is kept while the rows stay the same, so a figure that lost
        its tone gives the colour back."""
        if label is None:
            return
        colour = _tone_colour(tone)
        if colour is None:
            label.setPalette(QPalette())
            return
        palette = QPalette(label.palette())
        palette.setColor(QPalette.ColorRole.WindowText, colour)
        label.setPalette(palette)
