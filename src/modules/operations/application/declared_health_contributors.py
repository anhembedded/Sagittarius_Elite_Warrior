"""The health contributors the modules declared, built when first asked for (`EPIC-038C`).

`operations` reads the shell's table of declarations (`IHealthContributorTable`)
and turns each factory into a contributor with the finished container behind a
`PortResolver` - the moment a declaration made during registration can finally
resolve what it reads. It happens once, the first time the snapshot is published
(after every module has booted), and the result is kept.

A factory that fails (a port it needs is not bound) does not take the snapshot
down and is not hidden: its section is published `unavailable`, which `status`
turns into exit 11. That is the same rule a contributor that raises gets.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.core.contracts.i_health_contributor import (
    IHealthContributor,
    IHealthContributors,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_operations_registry import (
    HealthContributorDescriptor,
    IHealthContributorTable,
    PortResolver,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue


class _BrokenContributor(IHealthContributor):
    """Stands for a contributor whose factory failed: asked, it raises."""

    def __init__(self, name: str, failure: Exception) -> None:
        self._name = name
        self._failure = failure

    @property
    def name(self) -> str:
        return self._name

    def snapshot(self) -> Mapping[str, JsonValue]:
        raise self._failure


class DeclaredHealthContributors(IHealthContributors):
    """Builds the declared contributors on first use."""

    def __init__(self, table: IHealthContributorTable, resolver: PortResolver) -> None:
        self._table = table
        self._resolver = resolver
        self._lock = threading.Lock()
        self._built: tuple[IHealthContributor, ...] | None = None

    def contributors(self) -> tuple[IHealthContributor, ...]:
        with self._lock:
            if self._built is None:
                self._built = tuple(
                    self._build(descriptor)
                    for descriptor in self._table.health_descriptors()
                )
            return self._built

    def _build(self, descriptor: HealthContributorDescriptor) -> IHealthContributor:
        try:
            contributor = descriptor.factory(self._resolver)
        except Exception as failure:  # noqa: BLE001 - the seam: a factory's failure becomes its section
            return _BrokenContributor(descriptor.name, failure)
        if contributor.name != descriptor.name:
            return _BrokenContributor(
                descriptor.name,
                ValueError(
                    f"{descriptor.contributor_id!r} declared the section "
                    f"{descriptor.name!r} but built one named {contributor.name!r}"
                ),
            )
        return contributor
