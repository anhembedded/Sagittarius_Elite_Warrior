"""`EPIC-029F` — the Bots presenter's pacing and clock, apart from its wiring.

Named once here so the presenter's own file holds what it orchestrates, not
the numbers it paces itself by (`architecture-rule.md` §5.4: the presenter was
at its size threshold when `EPIC-034D` added the Connect step).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from PySide6.QtCore import QObject, QTimer
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)

#: The action tracker's key: one command in flight at a time.
ACTION = "bot_action"
#: A burst of store writes (a fill books, then the level moves) is one read.
COALESCE_MS = 150
#: Edits are judged once typing pauses.
REJUDGE_MS = 150
#: The running time ticks in minutes.
CLOCK_MS = 30_000


class BotsClock(QTimer):
    """The screen's clock: each beat recomputes the detail (the running time ticks), and on a
    read-only copy it also re-reads the bots (`BUG-227`). The writing copy hears its own saves as
    `BotChangedEvent`; a read-only copy shares no bus with the copy that writes, so without this
    beat its table would keep the figures of the moment it opened."""

    def __init__(
        self,
        parent: QObject,
        instance: IInstanceAccess,
        reread_bots: Callable[[], None],
        refresh_detail: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self.setInterval(CLOCK_MS)
        self.timeout.connect(refresh_detail)
        if instance.read_only:
            self.timeout.connect(reread_bots)


def utc_now() -> datetime:
    return datetime.now(UTC)
