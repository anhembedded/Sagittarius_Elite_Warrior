"""`StrategyArmingControlAdapter` — implements trading's
`IStrategyArmingControl` by wrapping `strategy`'s own, unchanged
`IStrategyArming`.

@details `DECISION_2026-09-17_strategy_ui_contributes_rather_than_being_imported.md`
§8. Bound in `StrategyModule.register()` (`composition/port_bindings.py`).
`arm()`'s translation is where `LiveStrategyConfig.__post_init__`'s
range/interval validation still runs, unchanged, by construction: it is
inside `to_live_strategy_config()`, which this adapter calls before ever
reaching `strategy`'s own `arm()`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.strategy.adapters.live_strategy_config_translation import (
    to_armed_config,
    to_live_strategy_config,
    to_trading_arm_block_reason,
    to_trading_disarm_block_reason,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_arming import (
    IStrategyArming,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_config import (
    ArmedStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_strategy_arming_control import (
    IStrategyArmingControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_arm_result import (
    ArmStrategyResult as TradingArmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_disarm_result import (
    DisarmStrategyResult as TradingDisarmStrategyResult,
)


class StrategyArmingControlAdapter(IStrategyArmingControl):
    """Translates arm/disarm/recall across the trading/strategy boundary."""

    def __init__(self, arming: IStrategyArming) -> None:
        self._arming = arming

    def arm(self, config: ArmedStrategyConfig) -> TradingArmStrategyResult:
        result = self._arming.arm(to_live_strategy_config(config))
        return TradingArmStrategyResult(
            armed=result.armed,
            block_reason=to_trading_arm_block_reason(result.block_reason),
            error_message=result.error_message,
        )

    def disarm(self) -> TradingDisarmStrategyResult:
        result = self._arming.disarm()
        return TradingDisarmStrategyResult(
            disarmed=result.disarmed,
            block_reason=to_trading_disarm_block_reason(result.block_reason),
        )

    def saved_selection(self) -> ArmedStrategyConfig:
        return to_armed_config(self._arming.saved_selection())
