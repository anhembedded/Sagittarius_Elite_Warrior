"""`IArmedStrategy` — what the live session has armed, for readers outside.

This module's first published port, and for a while its only one: PR 2.1c
measured that the `IStrategyCatalog` HLD §3.4 also plans would have had no
consumer it could serve alone, because every caller that reads the strategy keys
also needs the strategy *classes* (`EPIC-025C` §5).

Read-only, and that is the whole point: `arm()` and `disarm()` stay unpublished.
They are dispatched as `ArmStrategyCommand` / `DisarmStrategyCommand`, which run
validation, claim the symbol and publish events; a port method that armed a
strategy would be a second way in, past all of it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.armed_strategy_snapshot import (
    ArmedStrategySnapshot,
)


class IArmedStrategy(ABC):
    """The live session's armed state, safe to read from any thread."""

    @abstractmethod
    def armed(self) -> ArmedStrategySnapshot:
        """Both facts at one instant — see `ArmedStrategySnapshot` for why they
        are one call and not two."""
        ...
