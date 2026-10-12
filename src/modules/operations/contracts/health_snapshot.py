"""The health snapshot: what a host knows about itself, as one value (`EPIC-038C`).

Written by the host every health interval (`FileHealthSnapshotSink` puts it at
`state/health.json`) and read by a second process (`status`). Because a second
process reads it, its shape is a contract: a field is added within a version,
never renamed (`SCHEMA`).

@par Why the contributors' sections are nested under `sections`
A contributor is named by its module and a new module may choose any word; at the
top level one called `pid` or `written_at` would overwrite a field the reader
trusts. Nested, no name can.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)

SCHEMA = "sew.health/1"

#: Seconds between the snapshots a host writes. `status` judges freshness by the
#: interval each snapshot carries, so changing this needs no change to a reader.
HEALTH_INTERVAL_SECONDS = 10

#: A section whose contributor did not answer carries this under `status`.
UNAVAILABLE = "unavailable"
STATUS_KEY = "status"
REASON_KEY = "reason"


def unavailable_section(reason: str) -> dict[str, JsonValue]:
    """The section a failed contributor leaves: it says so and why, never a guess."""
    return {STATUS_KEY: UNAVAILABLE, REASON_KEY: reason}


def is_unavailable(section: Mapping[str, JsonValue]) -> bool:
    return section.get(STATUS_KEY) == UNAVAILABLE


@dataclass(frozen=True, slots=True)
class HealthSnapshot:
    """One moment of one host."""

    app_version: str
    pid: int
    started_at: datetime
    written_at: datetime
    #: How often this host writes, so a reader judges freshness by the host's
    #: own cadence and not by its guess of it.
    interval_s: int
    host_state: HostState
    sections: Mapping[str, Mapping[str, JsonValue]]

    def __post_init__(self) -> None:
        object.__setattr__(self, "sections", MappingProxyType(dict(self.sections)))

    @property
    def unavailable_sections(self) -> tuple[str, ...]:
        return tuple(
            name for name, section in self.sections.items() if is_unavailable(section)
        )
