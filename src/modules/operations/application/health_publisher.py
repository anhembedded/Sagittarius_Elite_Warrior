"""Build the host's health snapshot and hand it to a sink (`EPIC-038C`).

The publisher names no contributor and no sink: it asks every contributor the
shell collected (`IHealthContributors`) and publishes through whatever
`IHealthSnapshotSink` it was given. `test_a_new_contributor_needs_no_edit_to_the_publisher`
adds a fourth section with a test-only contributor and finds it in the snapshot.

The host state (`HostState`) is the caller's to say: a plain application that
publishes (the GUI, a one-shot command) says `SERVING` while it lives and
`STOPPED` when it ends; the `run` host (`EPIC-038D`) will say all five.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.core.contracts.i_health_contributor import (
    IHealthContributors,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_section_collector import (
    HealthSectionCollector,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.health_snapshot import (
    HealthSnapshot,
    unavailable_section,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_health_snapshot_sink import (
    IHealthSnapshotSink,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)


@dataclass(frozen=True, slots=True)
class HostIdentity:
    """What stays the same across one host's snapshots."""

    app_version: str
    pid: int
    started_at: datetime
    #: Seconds between snapshots; written into each so a reader need not guess.
    interval_s: int


class HealthPublisher:
    """Collects the sections and publishes one snapshot per call."""

    def __init__(
        self,
        contributors: IHealthContributors,
        sink: IHealthSnapshotSink,
        collector: HealthSectionCollector,
        clock: IOperationsClock,
        identity: HostIdentity,
    ) -> None:
        self._contributors = contributors
        self._sink = sink
        self._collector = collector
        self._clock = clock
        self._identity = identity

    def publish(self, host_state: HostState) -> HealthSnapshot:
        snapshot = HealthSnapshot(
            app_version=self._identity.app_version,
            pid=self._identity.pid,
            started_at=self._identity.started_at,
            written_at=self._clock.now(),
            interval_s=self._identity.interval_s,
            host_state=host_state,
            sections=self._sections(),
        )
        self._sink.publish(snapshot)
        return snapshot

    def _sections(self) -> dict[str, Mapping[str, JsonValue]]:
        sections: dict[str, Mapping[str, JsonValue]] = {}
        for contributor in self._contributors.contributors():
            name = contributor.name
            if name in sections:
                sections[f"{name}#duplicate"] = unavailable_section(
                    f"a second contributor is also named {name!r}"
                )
                continue
            sections[name] = self._collector.collect(contributor)
        return sections
