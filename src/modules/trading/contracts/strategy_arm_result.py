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

    SESSION_NOT_READY = "session_not_ready"
    POSITION_OPEN = "position_open"
    STRATEGY_NOT_FOUND = "strategy_not_found"
    INVALID_PARAMS = "invalid_params"
    MISSING_SYMBOL_OR_INTERVAL = "missing_symbol_or_interval"
    SYMBOL_LEASED = "symbol_leased"
    #: `EPIC-027N` — mirrors `strategy.contracts.arm_strategy_result`'s
    #: identical member of the same name; see this file's own module
    #: docstring for why the two enums declare the same set by value rather
    #: than one importing the other.
    SPOT_LEVERAGE_NOT_SUPPORTED = "spot_leverage_not_supported"
    SPOT_SHORT_NOT_SUPPORTED = "spot_short_not_supported"
    SPOT_QUOTE_ASSET_NOT_SUPPORTED = "spot_quote_asset_not_supported"


@dataclass(frozen=True)
class ArmStrategyResult:
    armed: bool
    block_reason: ArmStrategyBlockReason | None = None
    #: The rejecting exception's own text when `block_reason` is
    #: `INVALID_PARAMS`, so the UI can show which field was wrong instead
    #: of a generic "invalid parameters"; the refusal's words for
    #: `SESSION_NOT_READY`.
    error_message: str | None = None
