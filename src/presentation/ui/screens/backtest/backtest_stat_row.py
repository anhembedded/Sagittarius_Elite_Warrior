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
the "per-widget property" half of that same rule. The two colours come from
`semantic_colour()`, `kit/style.py`'s documented escape hatch for a colour
chosen per instance rather than per role, whose own docstring names this case;
a literal would fail the guard `EPIC-007D` drove to zero. Nothing else here is
coloured, no stylesheet is set, and `Palette` is not imported: every other pixel
is the platform's theme, and this file adds to none of §11.4's four numbers.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import Tone, semantic_colour

#: The two semantic-colour names this file reads, and the only two. Named
#: `_COLOUR` rather than `_TOKEN` because ruff's `S105` reads any
#: `*_TOKEN = "..."` as a possible hardcoded credential. `semantic_colour()` is
#: `kit/style.py`'s own documented escape hatch for *"a colour chosen per
#: instance rather than per role"*, and its docstring names this exact case:
#: whether a figure reads positive or negative is decided per figure at
#: runtime. A literal here would fail the no-hardcoded-colour guard
#: `EPIC-007D` drove to zero, and would not survive a palette change.
_GAIN_COLOUR = "success"
_LOSS_COLOUR = "danger"

_TITLE_KEY = "title"
_VALUE_KEY = "value"
_SUFFIX_KEY = "suffix"
_VALUE_TONE_KEY = "valueTone"
_BADGE_TEXT_KEY = "badgeText"
_BADGE_TONE_KEY = "badgeTone"


def _tone_colour(value: object) -> QColor | None:
    """The colour a tone carries, or `None` for "no verdict".

    `None` leaves the label on the platform's own text colour, which is what
    `Tone.NEUTRAL`, a missing key and a value that is not a `Tone` at all all
    mean — the same fallback every card dict upstream already assumes.
    """
    if value is Tone.POSITIVE:
        return QColor(semantic_colour(_GAIN_COLOUR))
    if value is Tone.NEGATIVE:
        return QColor(semantic_colour(_LOSS_COLOUR))
    return None


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
        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(24)
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

        for index, card in enumerate(self._get_cards()):
            self._row.addWidget(self._tile(index, card))
        # Leftover width stays empty on the right rather than stretching the
        # tiles, which is what every previous version of this row did.
        self._row.addStretch(1)

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
