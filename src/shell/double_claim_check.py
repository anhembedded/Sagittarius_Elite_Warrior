"""No two modules may claim the same abstract type (SDD boot step 4).

Two modules that both register `IMarketDataRepository` do not fail today: the
second one silently wins, and which one that is depends on the order of a list
nobody thinks of as ordering behaviour. This turns that into a boot-time error,
before `boot()` runs and before anything resolves, with both module ids in the
message.

It consumes the claims a `RegisteringContainer` recorded while each module's
`register()` ran, rather than reading the container afterwards — the container
cannot distinguish two lazy singleton registrations of the same type, so "who
claimed what" only exists if something writes it down as it happens.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field


class DoubleClaimError(RuntimeError):
    """Two modules registered the same abstract type."""


@dataclass
class DoubleClaimCheck:
    """Records who claimed what, module by module, and fails on the second claim."""

    _owner_of: dict[type, str] = field(default_factory=dict)

    def record(self, module_id: str, claims: Iterable[type]) -> None:
        """Attribute `claims` to `module_id`, failing on a type another module
        already claimed. Re-registering a type this module already owns is
        allowed: a module overriding itself is its own business."""
        for abstract in claims:
            previous = self._owner_of.get(abstract)
            if previous is None:
                self._owner_of[abstract] = module_id
            elif previous != module_id:
                raise DoubleClaimError(
                    f"{_name(abstract)} is registered by both {previous!r} and "
                    f"{module_id!r}. One abstract type has exactly one owning module; "
                    f"if both need it, the type belongs in a contracts/ package and "
                    f"one module provides it."
                )

    def owner_of(self, abstract: type) -> str | None:
        return self._owner_of.get(abstract)

    def claimed_types(self) -> tuple[type, ...]:
        return tuple(self._owner_of)


def _name(abstract: type) -> str:
    return getattr(abstract, "__name__", repr(abstract))
