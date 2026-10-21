"""`EPIC-034C` — what each `SessionBlockReason` says, in one place.

@details Three callers show a refusal of `ensure_ready()` and each used to need
its own copy of the words: the desk's order panel (a manual order), the Bots
mode's start refusal and its strategy arm refusal. They are the sentences the
Enable trading switch showed (`EPIC-021G`), reworded only where they named the
switch. The table is plain data so a caller outside `ui/` can use it; the
screens wrap it in an `EnumLabels` (`session_outcome_text.py`), which refuses an
incomplete table at import.
"""

from __future__ import annotations

from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_ready_result import (
    SessionBlockReason,
    SessionReadyResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.unexplained_position import (
    PositionUnexplainedWhy,
    UnexplainedPosition,
)

SESSION_BLOCK_WORDS: Mapping[SessionBlockReason, str] = {
    SessionBlockReason.TRADING_VENUE_DISABLED: "This venue cannot place orders.",
    SessionBlockReason.CONNECTION_NOT_READY: (
        "Connection to the exchange is not ready — check your API key/network connection."
    ),
    SessionBlockReason.UNEXPECTED_POSITIONS: (
        "The account has unexpected open positions — please handle them manually "
        "on the exchange before starting a bot, arming a strategy or placing an order."
    ),
    SessionBlockReason.SUPERSEDED_BY_CONCURRENT_STATE_CHANGE: (
        "Another operation (usually EMERGENCY STOP) changed the state while the "
        "account was being checked — nothing was started. Check the state and "
        "try again if you still want to."
    ),
    SessionBlockReason.EMERGENCY_STOP_IN_PROGRESS: (
        "An Emergency stop is still running on this venue — wait for it to "
        "finish, then try again."
    ),
}

#: `BUG-250` — what is said of one position an opening would not excuse. A complete table, one
#: sentence a reason (`test_session_block_words`).
UNEXPLAINED_POSITION_WORDS: Mapping[PositionUnexplainedWhy, str] = {
    PositionUnexplainedWhy.NO_CLAIM: "{symbol} holds {exchange} and no bot of this venue claims it",
    PositionUnexplainedWhy.DIFFERS_FROM_HISTORY: (
        "{symbol} holds {exchange} but the claiming bot's own orders account for {derived}"
    ),
    PositionUnexplainedWhy.HISTORY_UNVERIFIABLE: (
        "{symbol} holds {exchange} and the order history that would explain it could not be read"
    ),
}


def unexplained_position_words(position: UnexplainedPosition) -> str:
    """One position the opening would not excuse, with its figures."""
    return UNEXPLAINED_POSITION_WORDS[position.why].format(
        symbol=position.symbol,
        exchange=f"{position.exchange_quantity:f}",
        derived="nothing"
        if position.derived_quantity is None
        else f"{position.derived_quantity:f}",
    )


def refusal_words(result: SessionReadyResult) -> str:
    """The sentence for a refused `ensure_ready()`; for positions the opening would not excuse,
    followed by each one's symbol and figures (`BUG-250`).

    @raise ValueError `result` was not a refusal: asking for the words of a
    success is a caller's mistake, never an empty string to show.
    """
    if result.block_reason is None:
        raise ValueError("the session opened; there is no refusal to word")
    words = SESSION_BLOCK_WORDS[result.block_reason]
    if not result.unexplained_positions:
        return words
    detail = "; ".join(
        unexplained_position_words(p) for p in result.unexplained_positions
    )
    return f"{words} ({detail})"
