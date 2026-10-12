"""The snapshot as the JSON object `state/health.json` holds (`EPIC-038C`)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.health_snapshot import (
    SCHEMA,
    HealthSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_health_snapshot_source import (
    HealthSnapshotUnreadableError,
)


def encode(snapshot: HealthSnapshot) -> dict[str, JsonValue]:
    return {
        "schema": SCHEMA,
        "app_version": snapshot.app_version,
        "pid": snapshot.pid,
        "started_at": _iso(snapshot.started_at),
        "written_at": _iso(snapshot.written_at),
        "interval_s": snapshot.interval_s,
        "host_state": snapshot.host_state.value,
        "sections": {
            name: dict(section) for name, section in snapshot.sections.items()
        },
    }


def decode(document: object) -> HealthSnapshot:
    """@raise HealthSnapshotUnreadableError Not a snapshot of this schema."""
    if not isinstance(document, dict):
        raise HealthSnapshotUnreadableError("the snapshot is not a JSON object")
    if document.get("schema") != SCHEMA:
        raise HealthSnapshotUnreadableError(
            f"the snapshot's schema is {document.get('schema')!r}, not {SCHEMA!r}"
        )
    try:
        sections = document["sections"]
        if not isinstance(sections, dict):
            raise TypeError("sections is not an object")
        return HealthSnapshot(
            app_version=str(document["app_version"]),
            pid=int(document["pid"]),
            started_at=_moment(document["started_at"]),
            written_at=_moment(document["written_at"]),
            interval_s=int(document["interval_s"]),
            host_state=HostState(document["host_state"]),
            sections=cast("dict[str, dict[str, JsonValue]]", sections),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HealthSnapshotUnreadableError(
            f"the snapshot is malformed: {exc!r}"
        ) from exc


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _moment(raw: object) -> datetime:
    return datetime.fromisoformat(str(raw))
