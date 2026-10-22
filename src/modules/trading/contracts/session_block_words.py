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

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connection_failure_words import (
    CONNECTION_FAILURE_SENTENCES,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
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
    PositionUnexplainedWhy.NO_CLAIM_OFFERED: (
        "{symbol} holds {exchange}; only a bot's own Resume or Stop can open the session over a "
        "position, and this action offers none"
    ),
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


def _pause_words(result: SessionReadyResult) -> str:
    """What to do about an exchange pause: wait as long as it said. A ban lasts minutes to days, so
    it is never called a few seconds."""
    seconds = result.connection_retry_after
    if seconds is None:
        return "Wait for the pause to end, then try again."
    whole = int(-(-seconds.total_seconds() // 1))
    what = (
        "banned this address for"
        if result.connection_banned
        else "asked for a pause of"
    )
    return f"The exchange {what} {whole} s: try again after that."


def _connection_words(result: SessionReadyResult) -> str:
    """What the connection check found, when it named a failure: the cause, not a guess at the key.
    Empty when the refusal is not a connection one or the check named nothing."""
    kind = result.connection_failure
    if (
        result.block_reason is not SessionBlockReason.CONNECTION_NOT_READY
        or kind is None
    ):
        return ""
    words = (
        f"Connection to the exchange is not ready: {CONNECTION_FAILURE_SENTENCES[kind]}"
    )
    if kind is ConnectionFailureKind.RATE_LIMITED:
        return f"{words} {_pause_words(result)}"
    if kind is ConnectionFailureKind.NETWORK:
        return f"{words} If the host has only just started, try again in a few seconds."
    return words


def refusal_words(result: SessionReadyResult) -> str:
    """The sentence for a refused `ensure_ready()`; for positions the opening would not excuse,
    followed by each one's symbol and figures (`BUG-250`).

    @raise ValueError `result` was not a refusal: asking for the words of a
    success is a caller's mistake, never an empty string to show.
    """
    if result.block_reason is None:
        raise ValueError("the session opened; there is no refusal to word")
    words = _connection_words(result) or SESSION_BLOCK_WORDS[result.block_reason]
    if not result.unexplained_positions:
        return words
    detail = "; ".join(
        unexplained_position_words(p) for p in result.unexplained_positions
    )
    return f"{words} ({detail})"
