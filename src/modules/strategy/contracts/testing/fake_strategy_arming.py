"""`FakeStrategyArming` — `IStrategyArming`'s verified fake.

A test scripts arm/disarm outcomes and the last-saved selection; nothing
here dispatches a command or touches `LiveStrategySession`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.arm_strategy_result import (
    ArmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.disarm_strategy_result import (
    DisarmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_arming import (
    IStrategyArming,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)

_NOTHING_SAVED = LiveStrategyConfig(strategy_key="", symbol="", interval="")


class FakeStrategyArming(IStrategyArming):
    def __init__(self) -> None:
        self._arm_result = ArmStrategyResult(armed=True)
        self._disarm_result = DisarmStrategyResult(disarmed=True)
        self._saved = _NOTHING_SAVED
        #: What the test can assert was actually asked for.
        self.armed_with: LiveStrategyConfig | None = None
        self.disarm_calls = 0

    def script_arm(self, result: ArmStrategyResult) -> None:
        self._arm_result = result

    def script_disarm(self, result: DisarmStrategyResult) -> None:
        self._disarm_result = result

    def arm(self, config: LiveStrategyConfig) -> ArmStrategyResult:
        self.armed_with = config
        if self._arm_result.armed:
            self._saved = config
        return self._arm_result

    def disarm(self) -> DisarmStrategyResult:
        self.disarm_calls += 1
        return self._disarm_result

    def saved_selection(self) -> LiveStrategyConfig:
        return self._saved
