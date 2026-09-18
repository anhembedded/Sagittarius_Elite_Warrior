"""`DisarmStrategyResult` — trading's own copy of one `disarm()` outcome.

@details `IStrategyArmingControl.disarm()`'s return type; see
`armed_strategy_config.py` in this package for why trading owns a mirror
rather than importing `modules.strategy.contracts.disarm_strategy_result`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DisarmStrategyBlockReason(str, Enum):
    """@brief Why the strategy was not cleared."""

    TRADING_IS_ENABLED = "trading_is_enabled"


@dataclass(frozen=True)
class DisarmStrategyResult:
    disarmed: bool
    block_reason: DisarmStrategyBlockReason | None = None
