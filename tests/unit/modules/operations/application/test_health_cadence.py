"""The host's say over the snapshot: its interval, its state, what runs around it (`EPIC-038D`)."""

from __future__ import annotations

import logging
from datetime import timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_cadence import (
    CadenceHostHealth,
    HealthCadence,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_publisher import (
    HealthPublisher,
    HostIdentity,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_publishing import (
    HealthPublishing,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_section_collector import (
    HealthSectionCollector,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.health_snapshot import (
    HealthSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.status_world import (
    INTERVAL_S,
    NOW,
    FixedClock,
    FixedContributor,
    FixedContributors,
    RecordingSink,
)

_IDENTITY = HostIdentity("1.2.3", 4242, NOW - timedelta(hours=1), INTERVAL_S)


def _publishing(
    cadence: HealthCadence | None,
) -> tuple[HealthPublishing, RecordingSink]:
    sink = RecordingSink()
    publisher = HealthPublisher(
        FixedContributors(FixedContributor("bots", {"total": 1})),
        sink,
        HealthSectionCollector(0.5),
        FixedClock(),
        _IDENTITY,
    )
    return HealthPublishing(publisher, cadence), sink


def test_without_a_cadence_the_snapshot_says_serving_then_stopped() -> None:
    publishing, sink = _publishing(None)

    publishing.begin()
    publishing.tick()
    publishing.end()

    assert [s.host_state for s in sink.published] == [
        HostState.SERVING,
        HostState.SERVING,
        HostState.STOPPED,
    ]


def test_with_a_cadence_the_snapshot_says_what_the_host_says() -> None:
    cadence = HealthCadence(state=HostState.BOOTING)
    publishing, sink = _publishing(cadence)
    health = CadenceHostHealth(cadence)

    publishing.begin()
    health.set_state(HostState.SERVING)
    health.publish_now()
    health.set_state(HostState.DRAINING)
    health.publish_now()
    health.set_state(HostState.STOPPED)
    publishing.end()

    assert [s.host_state for s in sink.published] == [
        HostState.BOOTING,
        HostState.SERVING,
        HostState.DRAINING,
        HostState.STOPPED,
    ]


def test_a_host_that_failed_leaves_failed_not_stopped_as_its_last_word() -> None:
    cadence = HealthCadence(state=HostState.SERVING)
    publishing, sink = _publishing(cadence)
    publishing.begin()

    cadence.set_state(HostState.FAILED)
    publishing.end()

    assert sink.published[-1].host_state is HostState.FAILED


def test_the_probes_run_before_the_snapshot_and_the_line_after_it() -> None:
    cadence = HealthCadence()
    order: list[str] = []
    publishing, sink = _publishing(cadence)
    cadence.add_before(
        lambda: order.append(f"probe (snapshots so far: {len(sink.published)})")
    )
    cadence.add_after(
        lambda snapshot: order.append(f"line from {snapshot.host_state.value}")
    )

    publishing.tick()

    assert order == ["probe (snapshots so far: 0)", "line from SERVING"]


def test_the_begin_and_end_snapshots_run_no_hook() -> None:
    cadence = HealthCadence()
    order: list[str] = []
    cadence.add_before(lambda: order.append("probe"))
    cadence.add_after(lambda snapshot: order.append("line"))
    publishing, _ = _publishing(cadence)

    publishing.begin()
    publishing.end()

    assert order == []


def test_a_hook_that_raises_is_logged_and_the_snapshot_is_still_written(
    caplog: pytest.LogCaptureFixture,
) -> None:
    cadence = HealthCadence()
    seen: list[HealthSnapshot] = []

    def broken() -> None:
        raise RuntimeError("the probe fell over")

    cadence.add_before(broken)
    cadence.add_after(seen.append)
    publishing, sink = _publishing(cadence)

    with caplog.at_level(logging.ERROR, logger="App.Operations.Health"):
        publishing.tick()

    assert len(sink.published) == 1
    assert seen == sink.published  # the line still follows
    assert any("hook failed" in r.getMessage() for r in caplog.records)


def test_asking_for_a_snapshot_with_nothing_attached_does_nothing() -> None:
    """A read-only copy publishes nothing, and the host never runs on one."""
    HealthCadence().publish_now()


def test_attaching_makes_publish_now_a_snapshot() -> None:
    cadence = HealthCadence()
    _, sink = _publishing(cadence)

    cadence.publish_now()

    assert len(sink.published) == 1
