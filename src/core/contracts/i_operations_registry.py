"""Where a module declares what it contributes to running the app unattended.

`EPIC-038F`. The same inversion `ICliRegistry` makes for commands: **the module
declares, the shell collects.** `operations` reads the collected table and
imports no module that fills it, and no module imports `operations`.

The registry takes pre-flight checks (`EPIC-038F`) and health contributors
(`EPIC-038C`, `declare_health`); each kind is one method here and one table in
the shell's collector, and no declaration already made changed when the second
kind arrived.

A check is declared as a *factory*, not an instance: the module's
`declare_operations` runs while the application is being registered, before
anything can be resolved, so the factory is called at the moment `preflight`
runs, with the finished container behind a `PortResolver`.

Capability: Add a pre-flight check from the module that knows the thing, one class and one declaration
    Also: preflight, pre-flight check, declare_operations, readiness check, startup check, IPreflightCheck
    Use: IOperationsRegistry, PreflightCheckDescriptor, IPreflightCheck
    User: src/modules/trading/module.py
    Status: stable
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from Sagittarius_Elite_Warrior.src.core.contracts.i_health_contributor import (
    IHealthContributor,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_health_probe import IHealthProbe
from Sagittarius_Elite_Warrior.src.core.contracts.i_preflight_check import (
    IPreflightCheck,
)


class PortResolver(Protocol):
    """Hands out the application's published ports, as the container does.

    A `Protocol` for reason (c) of `architecture-rule.md` §2.1: the
    implementer is the Engine's container, a third-party class this package
    cannot make inherit from an ABC defined here.
    """

    def resolve[T](self, abstract: type[T]) -> T: ...


type PreflightCheckFactory = Callable[[PortResolver], IPreflightCheck]


@dataclass(frozen=True, slots=True)
class PreflightCheckDescriptor:
    """One check a module owns, ready for the shell's table."""

    #: Equal to the built check's `check_id`; the runner refuses a factory that disagrees.
    check_id: str
    factory: PreflightCheckFactory
    #: Which module declared it, so a clash names both sides.
    contributor_id: str


type HealthContributorFactory = Callable[[PortResolver], IHealthContributor]


@dataclass(frozen=True, slots=True)
class HealthContributorDescriptor:
    """One health section a module owns, ready for the shell's table.

    A factory for the reason a check is one: the declaration is made while the
    application is being registered; the contributor is built the first time the
    snapshot is published, when everything it reads can be resolved.
    """

    #: Equal to the built contributor's `name`; the section's key in the snapshot.
    name: str
    factory: HealthContributorFactory
    #: Which module declared it, so a clash names both sides.
    contributor_id: str


type HealthProbeFactory = Callable[[PortResolver], IHealthProbe]


@dataclass(frozen=True, slots=True)
class HealthProbeDescriptor:
    """One measurement a module takes for the host's health interval (`EPIC-038D`)."""

    #: Equal to the built probe's `name`; a second claim raises, as for a check.
    name: str
    factory: HealthProbeFactory
    #: Which module declared it, so a clash names both sides.
    contributor_id: str


class IOperationsRegistry(ABC):
    """What a module sees of the shell's operations table: declarations, no reads."""

    @abstractmethod
    def declare_preflight(self, descriptor: PreflightCheckDescriptor) -> None:
        """Claim `descriptor.check_id` for this module's check.

        Two modules claiming one id is a programming error, not a condition to
        resolve: the shell raises rather than letting the last one win.
        """

    @abstractmethod
    def declare_health(self, descriptor: HealthContributorDescriptor) -> None:
        """Claim the snapshot section `descriptor.name` for this module.

        A section name is an identity (it is a key in `health.json` and in
        `status --json`), so a second claim raises, naming both modules.
        """

    @abstractmethod
    def declare_probe(self, descriptor: HealthProbeDescriptor) -> None:
        """Claim the probe `descriptor.name` for this module (`EPIC-038D`).

        The `run` host calls every probe once per health interval, before it
        publishes; a second claim of one name raises, naming both modules.
        """


class IPreflightCheckTable(ABC):
    """What `operations` sees: the finished table, and no way to add to it."""

    @abstractmethod
    def descriptors(self) -> tuple[PreflightCheckDescriptor, ...]:
        """Every declared check, in a stable order (by id)."""


class IHealthContributorTable(ABC):
    """What `operations` sees of the health declarations: the finished table."""

    @abstractmethod
    def health_descriptors(self) -> tuple[HealthContributorDescriptor, ...]:
        """Every declared health contributor, in a stable order (by name)."""


class IHealthProbeTable(ABC):
    """What `operations` sees of the probe declarations: the finished table."""

    @abstractmethod
    def probe_descriptors(self) -> tuple[HealthProbeDescriptor, ...]:
        """Every declared probe, in a stable order (by name)."""
