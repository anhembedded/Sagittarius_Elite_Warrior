"""`EPIC-029F` — the Bots presenter's pacing and clock, apart from its wiring.

Named once here so the presenter's own file holds what it orchestrates, not
the numbers it paces itself by (`architecture-rule.md` §5.4: the presenter was
at its size threshold when `EPIC-034D` added the Connect step).
"""

from __future__ import annotations

from datetime import UTC, datetime

#: The action tracker's key: one command in flight at a time.
ACTION = "bot_action"
#: A burst of store writes (a fill books, then the level moves) is one read.
COALESCE_MS = 150
#: Edits are judged once typing pauses.
REJUDGE_MS = 150
#: The running time ticks in minutes.
CLOCK_MS = 30_000


def utc_now() -> datetime:
    return datetime.now(UTC)
