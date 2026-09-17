"""`IStrategyArming` — the write side of the live strategy session, matched
with the existing read-only `IArmedStrategy` (`EPIC-025`
`DECISION_2026-09-17_strategy_ui_contributes_rather_than_being_imported.md`,
O4/O6).

@details `IArmedStrategy`'s own docstring keeps `arm()`/`disarm()` off that
port so a read never doubles as a second way in past `ArmStrategyCommand`'s
validation; this is that command's own front door, published, because a
screen calling it is no longer the command's same module once `trading`,
`dashboard` and `backtest` are modules themselves. `saved_selection()`
replaces `LiveStrategyConfigStore.load()` for the same reason: an
`application/services/` object is no more reachable across a module
boundary than a `use_cases/` one.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.arm_strategy_result import (
    ArmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.disarm_strategy_result import (
    DisarmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)


class IStrategyArming(ABC):
    """Arm, disarm, and recall the last configuration the user chose."""

    @abstractmethod
    def arm(self, config: LiveStrategyConfig) -> ArmStrategyResult:
        """Dispatches `ArmStrategyCommand` and, on success, persists
        `config` as the one to restore next session. Persistence is not a
        separate step a caller can forget: it was the coordinator's job
        before this port existed, and every port implementer now owns it."""
        ...

    @abstractmethod
    def disarm(self) -> DisarmStrategyResult:
        """Dispatches `DisarmStrategyCommand`."""
        ...

    @abstractmethod
    def saved_selection(self) -> LiveStrategyConfig:
        """The last configuration a successful `arm()` persisted, or an
        empty `LiveStrategyConfig` when nothing has ever been saved — never
        `None`, so a screen restoring its card need not branch on absence
        the way `IArmedStrategy.armed()` already does not."""
        ...
