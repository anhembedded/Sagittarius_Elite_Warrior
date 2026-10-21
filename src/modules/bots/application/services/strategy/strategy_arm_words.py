"""`EPIC-045G` - the words of an arm's and a disarm's refusals, one table for the screen and the host.

The Bots tab's Arm strategy and Disarm strategy and the host's `bot arm-strategy` and `bot disarm-strategy`
ask the same `IStrategyArmingControl` and meet the same refusals. The sentences live here so the two
cannot tell an operator different things; the screen wraps the table in an `EnumLabels` (which checks that
every reason has a line, and which the application layer may not import), the host reads it directly and
`tests/unit/modules/bots/application/test_strategy_arm_words.py` checks the same completeness.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_arm_result import (
    ArmStrategyBlockReason,
)

ARM_BLOCK_WORDS: dict[ArmStrategyBlockReason, str] = {
    ArmStrategyBlockReason.SESSION_NOT_READY: "Trading could not start on this venue.",
    ArmStrategyBlockReason.POSITION_OPEN: (
        "A position is open on this symbol — close it (or use Emergency "
        "stop) before changing the strategy."
    ),
    ArmStrategyBlockReason.STRATEGY_NOT_FOUND: (
        "This strategy was not found in the registered list."
    ),
    ArmStrategyBlockReason.INVALID_PARAMS: "Strategy Parameters are invalid.",
    ArmStrategyBlockReason.MISSING_SYMBOL_OR_INTERVAL: (
        "Both symbol and trading timeframe must be selected."
    ),
    ArmStrategyBlockReason.SYMBOL_LEASED: (
        "This symbol is already being managed by another strategy — "
        "remove that one first, or choose a different symbol."
    ),
    ArmStrategyBlockReason.SPOT_LEVERAGE_NOT_SUPPORTED: (
        "Spot trading has no leverage — set leverage to 1x."
    ),
    ArmStrategyBlockReason.SPOT_SHORT_NOT_SUPPORTED: (
        "This strategy can open Short positions, which Spot does not "
        "support — choose a long-only strategy."
    ),
    ArmStrategyBlockReason.SPOT_QUOTE_ASSET_NOT_SUPPORTED: (
        "Spot trading currently supports USDT-quoted symbols only."
    ),
}

DISARM_BLOCKED_WORDS = (
    "A position is open on the strategy's symbol — close it (or use "
    "Emergency stop) before removing the strategy."
)
