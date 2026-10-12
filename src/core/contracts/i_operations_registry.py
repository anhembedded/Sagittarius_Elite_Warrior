"""Where a module declares what it contributes to running the app unattended.

`EPIC-038F`. The same inversion `ICliRegistry` makes for commands: **the module
declares, the shell collects.** `operations` reads the collected table and
imports no module that fills it, and no module imports `operations`.

Today the registry takes pre-flight checks. `EPIC-038C` adds health
contributors beside them (`declare_health`) when it lands; each is one more
method here and one more table in the shell's collector, and no declaration
already made changes.

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


class IOperationsRegistry(ABC):
    """What a module sees of the shell's operations table: declarations, no reads."""

    @abstractmethod
    def declare_preflight(self, descriptor: PreflightCheckDescriptor) -> None:
        """Claim `descriptor.check_id` for this module's check.

        Two modules claiming one id is a programming error, not a condition to
        resolve: the shell raises rather than letting the last one win.
        """


class IPreflightCheckTable(ABC):
    """What `operations` sees: the finished table, and no way to add to it."""

    @abstractmethod
    def descriptors(self) -> tuple[PreflightCheckDescriptor, ...]:
        """Every declared check, in a stable order (by id)."""
