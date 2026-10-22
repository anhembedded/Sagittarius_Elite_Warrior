"""English copy for `StrategyArmingCoordinator`'s arm/disarm refusals.

@details Split out of `strategy_arming_coordinator.py` (`EPIC-027N`) —
`architecture-rule.md` §5.4's shrink-only ratchet on that already-over-400-line
file left no room to grow it further, and a copy/label table is a different
abstraction level from the orchestration logic that reads it (`code/quality.md`
§6d) — the exact split `architecture-rule.md` §5 already prefers by default.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.strategy.strategy_arm_words import (
    ARM_BLOCK_WORDS,
    DISARM_BLOCKED_WORDS,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_arm_result import (
    ArmStrategyBlockReason,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.enum_labels import EnumLabels

#: English copy for each refusal, from the one table the host reads too (`EPIC-045G`). Every branch
#: of `ArmStrategyBlockReason` has a line - a missing one would surface as a silent no-op button, which
#: is the failure mode this whole epic exists to remove - and `EnumLabels` fails at import if one is missing.
ARM_BLOCK_MESSAGES = EnumLabels(ArmStrategyBlockReason, ARM_BLOCK_WORDS)
DISARM_BLOCKED_MESSAGE = DISARM_BLOCKED_WORDS
