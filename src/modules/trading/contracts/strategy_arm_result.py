"""`ArmStrategyResult` — trading's own copy of one `arm()` outcome.

@details `IStrategyArmingControl.arm()`'s return type; see
`armed_strategy_config.py` in this package for why trading owns a mirror
rather than importing `modules.strategy.contracts.arm_strategy_result`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ArmStrategyBlockReason(str, Enum):
    """@brief Why a strategy was not armed — named, never a bare `False`."""

    TRADING_IS_ENABLED = "trading_is_enabled"
    STRATEGY_NOT_FOUND = "strategy_not_found"
    INVALID_PARAMS = "invalid_params"
    MISSING_SYMBOL_OR_INTERVAL = "missing_symbol_or_interval"
    SYMBOL_LEASED = "symbol_leased"


@dataclass(frozen=True)
class ArmStrategyResult:
    armed: bool
    block_reason: ArmStrategyBlockReason | None = None
    #: The rejecting exception's own text when `block_reason` is
    #: `INVALID_PARAMS`, so the UI can show which field was wrong instead
    #: of a generic "invalid parameters".
    error_message: str | None = None
