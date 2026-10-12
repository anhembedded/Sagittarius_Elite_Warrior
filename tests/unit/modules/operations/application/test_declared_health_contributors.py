"""Declared contributors reach the snapshot, and `status`, with no edit to either (`EPIC-038C`)."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.i_health_contributor import (
    IHealthContributor,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_operations_registry import (
    HealthContributorDescriptor,
    PortResolver,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.file_health_snapshot_sink import (
    FileHealthSnapshotSink,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.file_health_snapshot_source import (
    FileHealthSnapshotSource,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.declared_health_contributors import (
    DeclaredHealthContributors,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_publisher import (
    HealthPublisher,
    HostIdentity,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_section_collector import (
    HealthSectionCollector,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.health_snapshot import (
    is_unavailable,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)
from Sagittarius_Elite_Warrior.src.shell.operations_registry import OperationsRegistry
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.status_world import (
    INTERVAL_S,
    NOW,
    FixedClock,
    FixedContributor,
    RecordingSink,
)


class _Resolver:
    """A `PortResolver` that hands out one marker object."""

    def __init__(self) -> None:
        self.resolved: list[type] = []

    def resolve[T](self, abstract: type[T]) -> T:
        self.resolved.append(abstract)
        raise LookupError(abstract.__name__)


def _declared(
    registry: OperationsRegistry, name: str, section: dict[str, int], owner: str = "x"
) -> None:
    registry.declare_health(
        HealthContributorDescriptor(
            name, lambda _r: FixedContributor(name, section), owner
        )
    )


def test_factories_run_on_first_use_not_when_declared() -> None:
    registry = OperationsRegistry()
    built: list[str] = []

    def factory(_resolver: PortResolver) -> IHealthContributor:
        built.append("built")
        return FixedContributor("late", {"n": 1})

    registry.declare_health(HealthContributorDescriptor("late", factory, "x"))
    contributors = DeclaredHealthContributors(registry, _Resolver())

    assert built == []
    assert [c.name for c in contributors.contributors()] == ["late"]
    contributors.contributors()
    assert built == ["built"]  # once, then kept


def test_a_factory_that_fails_is_an_unavailable_section_not_a_failed_snapshot() -> None:
    registry = OperationsRegistry()

    def needs_a_port(resolver: PortResolver) -> IHealthContributor:
        resolver.resolve(IHealthContributor)
        raise AssertionError("unreachable")

    registry.declare_health(HealthContributorDescriptor("broken", needs_a_port, "x"))
    _declared(registry, "fine", {"n": 1})
    publisher = _publisher(DeclaredHealthContributors(registry, _Resolver()))

    sections = publisher.publish(HostState.SERVING).sections

    assert is_unavailable(sections["broken"])
    assert sections["fine"] == {"n": 1}


def test_a_factory_that_builds_another_name_is_refused() -> None:
    registry = OperationsRegistry()
    registry.declare_health(
        HealthContributorDescriptor(
            "claimed", lambda _r: FixedContributor("other", {}), "x"
        )
    )

    sections = (
        _publisher(DeclaredHealthContributors(registry, _Resolver()))
        .publish(HostState.SERVING)
        .sections
    )

    assert is_unavailable(sections["claimed"])


def test_a_fourth_section_declared_through_the_registry_reaches_the_file_and_status(
    tmp_path: Path,
) -> None:
    registry = OperationsRegistry()
    for name in ("bots", "trading", "market_data"):
        _declared(registry, name, {"n": 1})
    _declared(registry, "fourth", {"anything": 7})
    path = tmp_path / "health.json"
    publisher = _publisher(
        DeclaredHealthContributors(registry, _Resolver()), FileHealthSnapshotSink(path)
    )

    publisher.publish(HostState.SERVING)

    read = FileHealthSnapshotSource(path).read()
    assert read is not None
    assert read.sections["fourth"] == {"anything": 7}
    assert list(json.loads(path.read_text(encoding="utf-8"))["sections"]) == [
        "bots",
        "fourth",
        "market_data",
        "trading",
    ]


def _publisher(
    contributors: DeclaredHealthContributors,
    sink: FileHealthSnapshotSink | None = None,
) -> HealthPublisher:
    return HealthPublisher(
        contributors,
        sink or RecordingSink(),
        HealthSectionCollector(0.5),
        FixedClock(),
        HostIdentity("1.2.3", 1, NOW - timedelta(hours=1), INTERVAL_S),
    )
