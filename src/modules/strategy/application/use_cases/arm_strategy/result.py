"""`EPIC-022B` — the outcome of one `ArmStrategyCommand`."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ArmStrategyBlockReason(str, Enum):
    """@brief Why a strategy was not armed — named, never a bare `False`,
    the same contract `EnableTradingBlockReason` follows."""

    #: Live trading is currently ON. Swapping the engine underneath an
    #: open position means the incoming strategy knows nothing about the
    #: entry that is already on the exchange, and the outgoing strategy's
    #: exit signal will never arrive — the position would be stranded with
    #: nobody planning to close it. The user turns trading off first;
    #: this is never overridden silently (`EPIC-022` §4.1).
    TRADING_IS_ENABLED = "trading_is_enabled"
    #: The key is not in `StrategyRegistry` — most often a saved config
    #: naming a strategy that has since been renamed or removed.
    STRATEGY_NOT_FOUND = "strategy_not_found"
    #: A parameter value the strategy rejected: an undeclared name, or one
    #: outside the `minval`/`maxval` its own `setup()` declared. The
    #: strategy itself is the validator (`BaseStrategy.__init__` raises);
    #: `error_message` carries its words, not a re-worded copy.
    INVALID_PARAMS = "invalid_params"
    #: Symbol or interval missing. An interval must never be guessed —
    #: `BUG-085`: a wrong interval is a wrong strategy, not a smaller one.
    MISSING_SYMBOL_OR_INTERVAL = "missing_symbol_or_interval"


@dataclass(frozen=True)
class ArmStrategyResult:
    armed: bool
    block_reason: ArmStrategyBlockReason | None = None
    #: The rejecting exception's own text when `block_reason` is
    #: `INVALID_PARAMS`, so the UI can show which field was wrong instead
    #: of a generic "invalid parameters".
    error_message: str | None = None
