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
}


def refusal_words(result: SessionReadyResult) -> str:
    """The sentence for a refused `ensure_ready()`.

    @raise ValueError `result` was not a refusal: asking for the words of a
    success is a caller's mistake, never an empty string to show.
    """
    if result.block_reason is None:
        raise ValueError("the session opened; there is no refusal to word")
    return SESSION_BLOCK_WORDS[result.block_reason]
