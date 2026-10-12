"""How `status` decides running, stale or not running (`EPIC-038C`, decision D5).

Two witnesses, neither enough alone. The lock is the liveness proof a crash
cannot fake: the operating system drops it when the process ends, however it
ends. The snapshot says what the host is doing, but a file outlives its writer.
So:

| Lock | Snapshot | Conclusion |
| :--- | :--- | :--- |
| free | any | `not running` - a fresh file with a free lock is a host that just died |
| held | written within three of its own intervals | `running` |
| held | older, missing or unreadable | `stale` - alive and not reporting |
"""

from __future__ import annotations

from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.health_snapshot import (
    HealthSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_liveness import (
    HostLiveness,
)

#: A snapshot older than this many of its own intervals is stale.
FRESH_INTERVALS = 3


def snapshot_age_s(snapshot: HealthSnapshot | None, now: datetime) -> int | None:
    if snapshot is None:
        return None
    return max(0, int((now - snapshot.written_at).total_seconds()))


def decide_liveness(
    lock_held: bool,
    snapshot: HealthSnapshot | None,
    snapshot_problem: str,
    now: datetime,
) -> tuple[HostLiveness, str]:
    """The liveness and the sentence that explains it."""
    if not lock_held:
        return HostLiveness.NOT_RUNNING, "no copy of the app holds the data root"
    if snapshot is None:
        return HostLiveness.STALE, snapshot_problem or (
            "a copy holds the data root and has published no health snapshot"
        )
    age = snapshot_age_s(snapshot, now)
    limit = FRESH_INTERVALS * snapshot.interval_s
    if age is not None and age > limit:
        return HostLiveness.STALE, (
            f"the last snapshot is {age}s old; this host writes one every "
            f"{snapshot.interval_s}s and a snapshot older than {limit}s is stale"
        )
    return HostLiveness.RUNNING, "a copy holds the data root and its snapshot is fresh"
