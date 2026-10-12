"""`EPIC-038C` - what `status` found."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusReport,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.health_snapshot import (
    HealthSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_liveness import (
    HostLiveness,
)


@dataclass(frozen=True, slots=True)
class HostStatus:
    """The observer's conclusion, and the facts it rests on."""

    liveness: HostLiveness
    #: One sentence saying why `liveness` is what it is.
    reason: str
    lock_held: bool
    #: The last snapshot the host published, `None` when there is none or it
    #: cannot be read (`reason` says which).
    snapshot: HealthSnapshot | None
    snapshot_age_s: int | None
    #: The bots, read from their files as a read-only copy reads them.
    bots: BotStatusReport
    checked_at: datetime
