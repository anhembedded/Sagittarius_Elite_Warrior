"""Dev Board's websocket status pill — text, a dot, and one honest colour.

`EPIC-015` Phase 4 made this `StatusPill.qml` inside a `QQuickWidget`, the
rollout's first QML panel embedded beside the live chart. `EPIC-025` PR 4.3l
deletes that (ADR D21) and this is what it takes: a dot and a label in a row.

Built here rather than in `kit/` because there is **one** consumer, which is
`base_feed`'s rule — and because the previous version's own docstring made the
same call and then said what would change it: *"Revisit if a third inline
`kit/` embed appears."* The progress banner did become shared (three callers,
`kit.ProgressBanner`); this did not.

## The tone vocabulary is not `Tone`'s

`Tone` answers positive / negative / neutral. This pill answers idle / active /
success / danger — a connection's state, which `dashboard_presenter.py`'s
`_WS_STATUS_BY_MODE` derives from `UIMode`. Mapping one onto the other would
lose "active", so the four names stay and this file reads their colours from
`semantic_colour()`, `kit/style.py`'s documented escape hatch for a colour
chosen per instance rather than per role.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import semantic_colour

_DOT = "●"
_IDLE_TONE = "idle"

#: Tone → the semantic-colour name its dot reads. `idle` is absent on purpose:
#: a connection that is not doing anything gets the platform's own text colour,
#: which is what "no verdict" looks like everywhere else in this app.
_COLOUR_BY_TONE = {
    "active": "accent",
    "success": "success",
    "danger": "danger",
}


class WsStatusPill(QWidget):  # base-exempt: a container, not a surface
    """
    @brief The websocket's state, as a coloured dot beside a word.

    @details Three plain setters, the same three the `.qml` had as properties,
    so `DevBoardPanel._sync_ws_status()` did not change: `set_text`,
    `set_tone`, `set_show_dot`. Deriving a tone from `UIMode` is the
    Presenter's, not this widget's.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statusPillWidget")

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self._dot = QLabel(_DOT)
        self._dot.setObjectName("statusPillDot")
        row.addWidget(self._dot)

        self._label = QLabel()
        self._label.setObjectName("statusPillLabel")
        row.addWidget(self._label)

        self.set_tone(_IDLE_TONE)

    def set_text(self, text: str) -> None:
        self._label.setText(text)

    def set_tone(self, tone: str) -> None:
        """@param tone One of "idle" | "active" | "success" | "danger" — the
        vocabulary `dashboard_presenter.py` maps `UIMode` onto. An unknown tone
        reads as `idle` rather than raising: a pill is a status readout, and
        failing to draw one would hide the status it exists to report."""
        name = _COLOUR_BY_TONE.get(tone)
        palette = QPalette(self._dot.palette())
        if name is None:
            palette = QPalette()
        else:
            palette.setColor(
                QPalette.ColorRole.WindowText, QColor(semantic_colour(name))
            )
        self._dot.setPalette(palette)

    def set_show_dot(self, show_dot: bool) -> None:
        self._dot.setVisible(show_dot)
