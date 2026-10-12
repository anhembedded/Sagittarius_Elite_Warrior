"""`status` as a `Report` and as an exit code (`EPIC-038C`).

One report feeds `--json` and the text view. The payload's keys are the
contract with monitors (`test_the_status_payload_keys_are_pinned`); the exit
code is the same facts read as a verdict:

| Liveness | Exit |
| :--- | :-: |
| running, every section answered | 0 |
| running, a section unavailable | 11 |
| stale | 11 |
| not running | 10 |
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import (
    JsonValue,
    Report,
    ReportCell,
    ReportRow,
    ReportSection,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.queries.get_host_status import (
    HostStatus,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_liveness import (
    HostLiveness,
)

COMMAND = "status"
SCHEMA_VERSION = 1


def status_report(status: HostStatus) -> Report:
    return Report(COMMAND, SCHEMA_VERSION, _payload(status), _layout(status))


def status_outcome(status: HostStatus) -> CliOutcome | None:
    """The exit code the findings deserve. The report was already printed, so the
    outcome carries no message."""
    if status.liveness is HostLiveness.NOT_RUNNING:
        return CliOutcome(ExitCode.HOST_NOT_RUNNING)
    if status.liveness is HostLiveness.STALE or _unavailable(status):
        return CliOutcome(ExitCode.HOST_UNHEALTHY)
    return None


def _unavailable(status: HostStatus) -> tuple[str, ...]:
    return () if status.snapshot is None else status.snapshot.unavailable_sections


def _payload(status: HostStatus) -> dict[str, JsonValue]:
    snapshot = status.snapshot
    host: dict[str, JsonValue] = {
        "state": status.liveness.value,
        "reason": status.reason,
        "lock_held": status.lock_held,
        "snapshot_age_s": status.snapshot_age_s,
        "host_state": None if snapshot is None else snapshot.host_state.value,
        "pid": None if snapshot is None else snapshot.pid,
        "app_version": None if snapshot is None else snapshot.app_version,
        "started_at": None if snapshot is None else _iso(snapshot.started_at),
        "written_at": None if snapshot is None else _iso(snapshot.written_at),
        "interval_s": None if snapshot is None else snapshot.interval_s,
    }
    sections: dict[str, JsonValue] = (
        {} if snapshot is None else {n: dict(s) for n, s in snapshot.sections.items()}
    )
    return {
        "host": host,
        "sections": sections,
        "unavailable_sections": list(_unavailable(status)),
        **status.bots.payload(),
        "counts": dict(status.bots.state_counts()),
    }


def _layout(status: HostStatus) -> tuple[ReportSection, ...]:
    snapshot = status.snapshot
    host_rows = [_field("State", status.liveness.value), _field("Why", status.reason)]
    if snapshot is not None:
        host_rows += [
            _field("Host", snapshot.host_state.value),
            _field("Pid", str(snapshot.pid)),
            _field("Version", snapshot.app_version),
            _field("Written", f"{status.snapshot_age_s}s ago"),
        ]
    sections = [ReportSection("Host", tuple(host_rows))]
    if snapshot is not None and snapshot.sections:
        sections.append(
            ReportSection(
                "Sections",
                tuple(
                    _field(name, json.dumps(dict(section), sort_keys=True))
                    for name, section in snapshot.sections.items()
                ),
            )
        )
    sections.append(ReportSection("Bots", (_field("Count", _counts(status)),)))
    return tuple(sections)


def _counts(status: HostStatus) -> str:
    counts = status.bots.state_counts()
    if not counts:
        return "none"
    return ", ".join(f"{state}: {count}" for state, count in counts.items())


def _field(label: str, value: str) -> ReportRow:
    return ReportRow((ReportCell(label, 10), ReportCell(value)))


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
