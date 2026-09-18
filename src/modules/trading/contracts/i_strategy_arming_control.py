"""`IStrategyArmingControl` — trading's own front door onto arming, disarming
and recalling the live strategy session, without naming the module that owns
it.

@details `DECISION_2026-09-17_strategy_ui_contributes_rather_than_being_imported.md`
§8 — see `i_armed_strategy_reader.py` in this package for the full boot-order
reasoning. `strategy`'s adapter
(`modules/strategy/adapters/strategy_arming_control_adapter.py`) implements
this port by translating `ArmedStrategyConfig` into its own
`LiveStrategyConfig` and back, at the boundary — that translation is where
`LiveStrategyConfig.__post_init__`'s range/interval validation still runs,
unchanged.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_config import (
    ArmedStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_arm_result import (
    ArmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_disarm_result import (
    DisarmStrategyResult,
)


class IStrategyArmingControl(ABC):
    """Arm, disarm, and recall the last configuration the user chose."""

    @abstractmethod
    def arm(self, config: ArmedStrategyConfig) -> ArmStrategyResult:
        """Dispatches the arming command and, on success, persists `config`
        as the one to restore next session."""
        ...

    @abstractmethod
    def disarm(self) -> DisarmStrategyResult:
        """Dispatches the disarming command."""
        ...

    @abstractmethod
    def saved_selection(self) -> ArmedStrategyConfig:
        """The last configuration a successful `arm()` persisted, or an
        empty `ArmedStrategyConfig` when nothing has ever been saved — never
        `None`, so a screen restoring its card need not branch on absence."""
        ...
