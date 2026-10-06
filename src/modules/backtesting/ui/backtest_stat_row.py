"""The Backtest screen's primary performance figures, as a row of read-only
tiles — `EPIC-025` PR 4.3g.

## What this replaces, and why it is not a card

`EPIC-006E` drew these as `MetricCard.qml`, `EPIC-007F` replaced that with the
QtWidgets `kit.StatCard`, and `EPIC-015` Phase 4 replaced *that* with
`StatCardRow.qml` (a `Repeater` of `StatCard.qml`). All three were cards: a
titled box with a border and a background. HLD §11.3 retires the card outright —
the user's judgement, *"các card cũ cũng rất là tệ"* — and offers a **read-only
summary** in its place. That is what this is: title over figure, four or five
across, no chrome of its own.

Its own file rather than another method on `BackTestTopPanel`, which is already
746 lines against `architecture-rule` §5's 400-line ceiling; adding to it would
make a pre-existing violation worse.

## Colour, and where this differs from PR 0.4b

ADR D21 leaves colour *only* where it carries meaning, and only through a
`QPalette` role or a per-widget property. PR 0.4b's database-status table
concluded from that rule that its health column should carry **no** colour,
because Qt has no palette role meaning "this shard has holes in it" and the
text (`"OK"` against `"3 gaps found!"`) already said it.

A profit figure is the other case. Green for gain and red for loss is a
convention of the domain this app is in, not decoration this screen invented, so
the tone survives — written onto the one label that carries the figure, which is
the "per-widget property" half of that same rule, in the colour `readout_table`
gives a verdict (the one the Trades table uses). Nothing else here is coloured,
no stylesheet is set: every other pixel is the platform's theme.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import (
    Tone,
    tone_colour,
)

_TITLE_KEY = "title"
_VALUE_KEY = "value"
_SUFFIX_KEY = "suffix"
_VALUE_TONE_KEY = "valueTone"
_BADGE_TEXT_KEY = "badgeText"
_BADGE_TONE_KEY = "badgeTone"
#: How many figures sit side by side.
TILES_PER_ROW = 2


def _tone_colour(value: object) -> QColor | None:
    """The colour a tone carries, or `None` for "no verdict".

    `None` leaves the label on the platform's own text colour, which is what
    `Tone.NEUTRAL`, a missing key and a value that is not a `Tone` at all all
    mean — the same fallback every card dict upstream already assumes.
    """
    return tone_colour(value) if isinstance(value, Tone) else None


class BacktestStatRow(QWidget):  # base-exempt: a container, not a surface
    """
    @brief One tile per primary performance figure, rebuilt when the run's
    numbers change.

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
        self._row = QGridLayout(self)
        self._row.setContentsMargins(0, 0, 0, 0)
        self.refresh()

    def refresh(self) -> None:
        """Re-pulls `get_cards()` and rebuilds the row."""
        while self._row.count():
            entry = self._row.takeAt(0)
            if entry is None:  # pragma: no cover — count() > 0 guarantees one
                break
            widget = entry.widget()
            if widget is not None:
                # Detached before the deferred delete: the main event loop
                # delivers that, not this call, so without it the previous
                # run's figures stay parented here in between.
                widget.setParent(None)
                widget.deleteLater()

        # Two tiles a row: the figures live in the Metrics dock, a side panel
        # (`EPIC-033L`), where four abreast took 563 px of a 1366 px window
        # and left the chart 558 (review of PR #355).
        for index, card in enumerate(self._get_cards()):
            row, column = divmod(index, TILES_PER_ROW)
            self._row.addWidget(self._tile(index, card), row, column)

    def _tile(self, index: int, card: Mapping[str, object]) -> QWidget:
        tile = QWidget()
        tile.setObjectName(f"cardMetric_{index}")
        column = QVBoxLayout(tile)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(2)

        title = QLabel(str(card.get(_TITLE_KEY, "")).upper())
        title.setObjectName(f"cardMetricTitle_{index}")
        column.addWidget(title)

        figure = str(card.get(_VALUE_KEY, ""))
        suffix = str(card.get(_SUFFIX_KEY, ""))
        value = QLabel(f"{figure}{suffix}")
        value.setObjectName(f"cardMetricValue_{index}")
        value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._paint(value, card.get(_VALUE_TONE_KEY))
        column.addWidget(value)

        badge_text = str(card.get(_BADGE_TEXT_KEY, ""))
        if badge_text:
            badge = QLabel(badge_text)
            badge.setObjectName(f"cardMetricBadge_{index}")
            self._paint(badge, card.get(_BADGE_TONE_KEY))
            column.addWidget(badge)

        return tile

    @staticmethod
    def _paint(label: QLabel, tone: object) -> None:
        """Writes a tone onto one label, or leaves the theme's colour alone."""
        colour = _tone_colour(tone)
        if colour is None:
            return
        palette = QPalette(label.palette())
        palette.setColor(QPalette.ColorRole.WindowText, colour)
        label.setPalette(palette)
