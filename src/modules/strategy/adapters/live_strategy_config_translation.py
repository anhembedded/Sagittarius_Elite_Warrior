"""Field-for-field translation between `strategy`'s own value types and the
trading-owned mirrors `modules/trading/contracts/` declares.

@details `DECISION_2026-09-17_strategy_ui_contributes_rather_than_being_imported.md`
§8: this is the one place `strategy` is allowed to know both shapes: it
already depends on `trading` (`strategy.dependencies` names it), so importing
`modules.trading.contracts` here costs nothing, and every adapter in this
package calls through here rather than repeating the field list.

The two enums translate by `.value`: `ArmStrategyBlockReason` and its
trading-owned mirror declare the identical set of string members on
purpose (see each file's own docstring for why the value is trading's real
name, not strategy's — a leaked implementation label would defeat the point
of a mirror).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.arm_strategy_result import (
    ArmStrategyBlockReason,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.disarm_strategy_result import (
    DisarmStrategyBlockReason,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_config import (
    ArmedStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_arm_result import (
    ArmStrategyBlockReason as TradingArmStrategyBlockReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_disarm_result import (
    DisarmStrategyBlockReason as TradingDisarmStrategyBlockReason,
)


def to_armed_config(config: LiveStrategyConfig) -> ArmedStrategyConfig:
    """`strategy`'s own value, as trading reads it."""
    return ArmedStrategyConfig(
        strategy_key=config.strategy_key,
        symbol=config.symbol,
        interval=config.interval,
        strategy_params=config.strategy_params,
        sizing_percent=config.sizing_percent,
        leverage=config.leverage,
    )


def to_live_strategy_config(config: ArmedStrategyConfig) -> LiveStrategyConfig:
    """Trading's value, turned back into the real thing — where
    `LiveStrategyConfig.__post_init__`'s range/interval validation runs."""
    return LiveStrategyConfig(
        strategy_key=config.strategy_key,
        symbol=config.symbol,
        interval=config.interval,
        strategy_params=config.strategy_params,
        sizing_percent=config.sizing_percent,
        leverage=config.leverage,
    )


def to_trading_arm_block_reason(
    reason: ArmStrategyBlockReason | None,
) -> TradingArmStrategyBlockReason | None:
    if reason is None:
        return None
    return TradingArmStrategyBlockReason(reason.value)


def to_trading_disarm_block_reason(
    reason: DisarmStrategyBlockReason | None,
) -> TradingDisarmStrategyBlockReason | None:
    if reason is None:
        return None
    return TradingDisarmStrategyBlockReason(reason.value)
