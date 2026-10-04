"""`EPIC-029F` — the bots' own log lines, for the selected bot's log tab.

Every bot writes `"Bot <id>: ..."` on an `App.Bots.*` logger (its worker, its
executor, its resume). A `SignalLogHandler` on `App.Bots` copies each INFO+
line onto the Qt thread through a queued signal, and detaches itself if the
screen is gone first; the screen keeps the latest lines and shows the
selected bot's. Bots log per action and per fill, never per tick at INFO, so
this is no hot path (`logging-rule.md` §6, `BUG-042`).
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.support.ui_kit.signal_log_handler import (
    SignalLogHandler,
)

#: The bots module's logger tree.
BOTS_LOGGER = "App.Bots"


class BotLogFeed(QObject):
    """@brief Copies `App.Bots` log lines onto the Qt thread."""

    #: One formatted line.
    line = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._handler = SignalLogHandler(self.line, BOTS_LOGGER)
        self._handler.setLevel(logging.INFO)
        self._handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S")
        )
        logging.getLogger(BOTS_LOGGER).addHandler(self._handler)

    def close(self) -> None:
        """Detaches the handler. Safe to call twice."""
        self._handler.detach()
