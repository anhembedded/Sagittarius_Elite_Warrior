"""`EPIC-022B` — the outcome of one `ArmStrategyCommand`."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ArmStrategyBlockReason(str, Enum):
    """@brief Why a strategy was not armed — named, never a bare `False`,
    the same contract `SessionBlockReason` follows."""

    #: The venue's order session could not be opened (`EPIC-034C`): the
    #: connection is not ready, the account holds a position this app did not
    #: open, or an Emergency Stop landed meanwhile. `error_message` carries the
    #: words (`session_block_words.py`), the ones the Enable switch used.
    SESSION_NOT_READY = "session_not_ready"
    #: This app has a position open on the symbol being armed, or on the symbol
    #: already armed (`EPIC-022` §4.1, restated by `EPIC-034C`). Swapping the
    #: engine underneath an open position means the incoming strategy knows
    #: nothing about the entry already on the exchange, and the outgoing
    #: strategy's exit signal will never arrive — the position would be stranded
    #: with nobody planning to close it. It was refused while trading was ON;
    #: with no switch the cause itself is what refuses. Never overridden silently.
    POSITION_OPEN = "position_open"
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
    #: `EPIC-025` PR 2.1f — somebody else holds `trading`'s lease on that
    #: symbol (`ITradingSession.claim_symbol`). Unreachable while only one
    #: strategy can be armed, and named anyway: the claim's contract can refuse,
    #: so a caller that pretended it could not would be the one left with a
    #: half-armed session when ADR §7 item 15's second strategy arrives.
    SYMBOL_LEASED = "symbol_leased"
    #: `EPIC-027N` AC1 — leverage is a sizing multiplier only on Spot (there is
    #: no margin to lever), fixed at `1`. A saved config naming anything else
    #: is refused rather than silently clamped — clamping would run the
    #: strategy at a sizing the user never chose.
    SPOT_LEVERAGE_NOT_SUPPORTED = "spot_leverage_not_supported"
    #: `EPIC-027N` AC2 (ADR O2) — the strategy's own `supported_directions`
    #: names `SHORT`; a live Spot account has no short side to open, so half
    #: of what the strategy would do could never run. Refused, not silently
    #: run long-only, so the user is never quietly given a different strategy
    #: than the one they picked.
    SPOT_SHORT_NOT_SUPPORTED = "spot_short_not_supported"
    #: `EPIC-027N` AC5 (ADR D9/O4) — Phase 1 Spot trades USDT-quoted pairs
    #: only; the session limits and sizing are already USDT-denominated
    #: (`config_keys.py`), and nothing in this phase converts a different
    #: quote asset's balance into USDT.
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
