"""What a module may say at `contribute()` time (HLD §4, SDD-01).

The registry is the **only** thing a module's `contribute()` receives, so this
port is the whole surface area of "a module adds UI". It takes descriptors and
gives nothing back: a module cannot enumerate other modules' contributions,
cannot reach a surface, and cannot build a widget here. Reading the registry is
the shell's job (`ContributionRegistry` adds the query side).

Validation happens in these calls, not at render time (pluggy's rule, HLD §7.3):
an unknown surface, a place the surface does not accept, or a duplicate
identity raises `ContributionError` while the stack still says which module
asked for it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.core.contracts.contribution_descriptor import (
    ContributionDescriptor,
)
from Sagittarius_Elite_Warrior.src.core.contracts.screen_contribution import (
    ScreenContribution,
)


class IContributionRegistry(ABC):
    @abstractmethod
    def contribute(self, descriptor: ContributionDescriptor) -> None:
        """Offer one widget to one place. Raises `ContributionError` if the
        descriptor names a surface or place that cannot hold it, or repeats an
        identity already registered. A contribution to a surface that exists but
        is gated off for this run is dropped with one log line, not an error."""

    @abstractmethod
    def contribute_screen(self, contribution: ScreenContribution) -> None:
        """Offer a whole navigable screen. Raises `ContributionError` on a
        duplicate route or a second default screen."""
