"""The publisher builds the snapshot from whatever contributors exist (`EPIC-038C`)."""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Mapping
from datetime import timedelta
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_health_contributor import (
    IHealthContributor,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.file_health_snapshot_sink import (
    REPLACE_ATTEMPTS,
    FileHealthSnapshotSink,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.file_health_snapshot_source import (
    FileHealthSnapshotSource,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_publisher import (
    HealthPublisher,
    HostIdentity,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_publishing import (
    HealthPublishing,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_section_collector import (
    FORBIDDEN_KEY_PARTS,
    HealthSectionCollector,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.health_snapshot import (
    HealthSnapshot,
    is_unavailable,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_health_snapshot_sink import (
    IHealthSnapshotSink,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.status_world import (
    INTERVAL_S,
    NOW,
    FixedClock,
    FixedContributor,
    FixedContributors,
    RecordingSink,
)

_DEADLINE_S = 0.05
_IDENTITY = HostIdentity("1.2.3", 4242, NOW - timedelta(hours=1), INTERVAL_S)


class RaisingContributor(IHealthContributor):
    @property
    def name(self) -> str:
        return "trading"

    def snapshot(self) -> Mapping[str, JsonValue]:
        raise ValueError("secret-looking-detail-123")


class BlockedContributor(IHealthContributor):
    """Answers only once `release` is set; the test sets it when it is done."""

    def __init__(self) -> None:
        self.release = threading.Event()
        self.asked = 0

    @property
    def name(self) -> str:
        return "market_data"

    def snapshot(self) -> Mapping[str, JsonValue]:
        self.asked += 1
        self.release.wait(timeout=30)
        return {"late": True}


def _publisher(
    *contributors: IHealthContributor,
) -> tuple[HealthPublisher, RecordingSink]:
    sink = RecordingSink()
    publisher = HealthPublisher(
        FixedContributors(*contributors),
        sink,
        HealthSectionCollector(_DEADLINE_S),
        FixedClock(),
        _IDENTITY,
    )
    return publisher, sink


def test_a_contributor_that_raises_is_unavailable_not_fatal(
    caplog: pytest.LogCaptureFixture,
) -> None:
    publisher, _ = _publisher(
        FixedContributor("bots", {"total": 2}), RaisingContributor()
    )

    with caplog.at_level("WARNING", logger="App.Operations.Health"):
        snapshot = publisher.publish(HostState.SERVING)

    assert snapshot.sections["bots"] == {"total": 2}
    assert is_unavailable(snapshot.sections["trading"])
    assert snapshot.sections["trading"]["reason"] == "raised ValueError"
    # The exception's text could hold anything; it is logged, never published.
    assert "secret-looking-detail-123" not in json.dumps(dict(snapshot.sections))
    assert "secret-looking-detail-123" in caplog.text


def test_a_slow_contributor_is_cut_off_at_its_deadline() -> None:
    blocked = BlockedContributor()
    publisher, _ = _publisher(FixedContributor("bots", {"total": 1}), blocked)
    try:
        snapshot = publisher.publish(HostState.SERVING)
        again = publisher.publish(HostState.SERVING)
    finally:
        blocked.release.set()

    assert snapshot.sections["bots"] == {"total": 1}
    assert is_unavailable(snapshot.sections["market_data"])
    assert "no answer within" in str(snapshot.sections["market_data"]["reason"])
    # Not asked again while the first question is still unanswered.
    assert is_unavailable(again.sections["market_data"])
    assert blocked.asked == 1


def test_a_new_contributor_needs_no_edit_to_the_publisher() -> None:
    publisher, sink = _publisher(
        FixedContributor("bots", {"total": 2}),
        FixedContributor("fourth", {"anything": 7}),
    )

    publisher.publish(HostState.SERVING)

    assert sink.published[0].sections["fourth"] == {"anything": 7}
    assert list(sink.published[0].sections) == ["bots", "fourth"]


def test_a_second_contributor_with_a_taken_name_is_reported_not_overwritten() -> None:
    publisher, sink = _publisher(
        FixedContributor("bots", {"total": 2}), FixedContributor("bots", {"total": 99})
    )

    publisher.publish(HostState.SERVING)

    sections = sink.published[0].sections
    assert sections["bots"] == {"total": 2}
    assert is_unavailable(sections["bots#duplicate"])


@pytest.mark.parametrize("part", FORBIDDEN_KEY_PARTS)
def test_a_section_naming_a_secret_or_a_balance_is_refused(part: str) -> None:
    publisher, _ = _publisher(
        FixedContributor("trading", {"nested": [{f"x_{part}_y": 1}]})
    )

    section = publisher.publish(HostState.SERVING).sections["trading"]

    assert is_unavailable(section)
    assert f"x_{part}_y" not in json.dumps(dict(section))


def test_a_section_json_cannot_hold_is_refused() -> None:
    publisher, _ = _publisher(FixedContributor("bots", {"when": NOW}))  # type: ignore[dict-item]

    assert is_unavailable(publisher.publish(HostState.SERVING).sections["bots"])


def test_the_snapshot_carries_the_hosts_identity_and_state() -> None:
    publisher, _ = _publisher()

    snapshot = publisher.publish(HostState.DRAINING)

    assert (snapshot.app_version, snapshot.pid, snapshot.interval_s) == (
        "1.2.3",
        4242,
        INTERVAL_S,
    )
    assert snapshot.host_state is HostState.DRAINING
    assert snapshot.written_at == NOW


def test_the_file_sink_round_trips_and_holds_no_secret(tmp_path: Path) -> None:
    path = tmp_path / "state" / "health.json"
    publisher = HealthPublisher(
        FixedContributors(FixedContributor("bots", {"total": 2})),
        FileHealthSnapshotSink(path),
        HealthSectionCollector(_DEADLINE_S),
        FixedClock(),
        _IDENTITY,
    )

    published = publisher.publish(HostState.SERVING)

    assert FileHealthSnapshotSource(path).read() == published
    document = json.loads(path.read_text(encoding="utf-8"))
    assert set(document) == {
        "schema", "app_version", "pid", "started_at", "written_at",
        "interval_s", "host_state", "sections",
    }  # fmt: skip
    assert document["schema"] == "sew.health/1"
    assert document["written_at"] == "2026-10-12T12:00:00Z"
    lowered = path.read_text(encoding="utf-8").lower()
    assert not [part for part in FORBIDDEN_KEY_PARTS if part in lowered]


def test_the_snapshot_is_written_atomically(tmp_path: Path) -> None:
    path = tmp_path / "health.json"
    clock = FixedClock()
    first = HealthPublisher(
        FixedContributors(FixedContributor("bots", {"total": 1})),
        FileHealthSnapshotSink(path),
        HealthSectionCollector(_DEADLINE_S),
        clock,
        _IDENTITY,
    )
    first.publish(HostState.SERVING)
    before = path.read_text(encoding="utf-8")

    def killed_before_the_rename(source: Path, target: Path) -> None:
        raise KeyboardInterrupt

    clock.current = NOW + timedelta(seconds=10)
    dying = HealthPublisher(
        FixedContributors(FixedContributor("bots", {"total": 2})),
        FileHealthSnapshotSink(path, replace=killed_before_the_rename),
        HealthSectionCollector(_DEADLINE_S),
        clock,
        _IDENTITY,
    )
    with pytest.raises(KeyboardInterrupt):
        dying.publish(HostState.SERVING)

    assert path.read_text(encoding="utf-8") == before
    assert FileHealthSnapshotSource(path).read() is not None
    assert (tmp_path / "health.json.tmp").exists()  # the next write replaces it


def test_a_reader_of_a_missing_file_gets_none(tmp_path: Path) -> None:
    assert FileHealthSnapshotSource(tmp_path / "absent.json").read() is None


def test_publishing_writes_serving_then_stopped_and_a_late_tick_cannot_undo_it() -> (
    None
):
    publisher, sink = _publisher()
    publishing = HealthPublishing(publisher)

    publishing.begin()
    publishing.tick()
    publishing.end()
    publishing.tick()
    publishing.end()

    assert [s.host_state for s in sink.published] == [
        HostState.SERVING,
        HostState.SERVING,
        HostState.STOPPED,
    ]


def test_a_failed_write_is_logged_and_does_not_stop_the_host(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class FullDisk(IHealthSnapshotSink):
        def publish(self, snapshot: HealthSnapshot) -> None:
            raise OSError("No space left on device")

    publishing = HealthPublishing(
        HealthPublisher(
            FixedContributors(),
            FullDisk(),
            HealthSectionCollector(_DEADLINE_S),
            FixedClock(),
            _IDENTITY,
        )
    )

    with caplog.at_level("ERROR", logger="App.Operations.Health"):
        publishing.begin()
        publishing.tick()

    assert caplog.text.count("[health-snapshot] could not write") == 2


@pytest.mark.parametrize(
    "key",
    ["profit", "unrealized_pnl", "realizedPnL", "listenKey", "listen_key", "Equity"],
)
def test_the_money_and_session_keys_the_port_promises_to_refuse_are_refused(
    key: str,
) -> None:
    publisher, _ = _publisher(FixedContributor("trading", {"venue": {key: 1}}))

    assert is_unavailable(publisher.publish(HostState.SERVING).sections["trading"])


def test_the_rename_is_retried_while_a_reader_holds_the_file_open(
    tmp_path: Path,
) -> None:
    path = tmp_path / "health.json"
    refusals = {"left": 3}
    renamed: list[Path] = []
    pauses: list[float] = []

    def refuse_while_a_reader_has_it_open(source: Path, target: Path) -> None:
        if refusals["left"]:
            refusals["left"] -= 1
            raise PermissionError(13, "The process cannot access the file")
        renamed.append(target)
        os.replace(source, target)

    sink = FileHealthSnapshotSink(
        path, replace=refuse_while_a_reader_has_it_open, sleep=pauses.append
    )
    publisher = HealthPublisher(
        FixedContributors(),
        sink,
        HealthSectionCollector(_DEADLINE_S),
        FixedClock(),
        _IDENTITY,
    )

    publisher.publish(HostState.SERVING)

    assert renamed == [path]
    assert len(pauses) == 3
    assert FileHealthSnapshotSource(path).read() is not None


def test_a_reader_that_never_lets_go_is_reported_after_the_bounded_retries(
    tmp_path: Path,
) -> None:
    attempts: list[int] = []
    pauses: list[float] = []

    def always_refuse(source: Path, target: Path) -> None:
        attempts.append(1)
        raise PermissionError(13, "in use")

    sink = FileHealthSnapshotSink(
        tmp_path / "health.json", replace=always_refuse, sleep=pauses.append
    )
    publisher = HealthPublisher(
        FixedContributors(),
        sink,
        HealthSectionCollector(_DEADLINE_S),
        FixedClock(),
        _IDENTITY,
    )

    with pytest.raises(PermissionError):
        publisher.publish(HostState.SERVING)

    assert len(attempts) == REPLACE_ATTEMPTS
    assert len(pauses) == REPLACE_ATTEMPTS - 1
