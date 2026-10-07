"""English copy for `StrategyArmingCoordinator`'s arm/disarm refusals.

@details Split out of `strategy_arming_coordinator.py` (`EPIC-027N`) —
`architecture-rule.md` §5.4's shrink-only ratchet on that already-over-400-line
file left no room to grow it further, and a copy/label table is a different
abstraction level from the orchestration logic that reads it (`code/quality.md`
§6d) — the exact split `architecture-rule.md` §5 already prefers by default.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_arm_result import (
    ArmStrategyBlockReason,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.enum_labels import EnumLabels

#: English copy for each refusal. Every branch of
#: `ArmStrategyBlockReason` has a line here — a missing one would surface
#: as a silent no-op button, which is the failure mode this whole epic
#: exists to remove.
ARM_BLOCK_MESSAGES = EnumLabels(
    ArmStrategyBlockReason,
    {
        ArmStrategyBlockReason.SESSION_NOT_READY: (
            "Trading could not start on this venue."
        ),
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
    },
)
DISARM_BLOCKED_MESSAGE = (
    "A position is open on the strategy's symbol — close it (or use "
    "Emergency stop) before removing the strategy."
)
