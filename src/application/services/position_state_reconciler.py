"""`EPIC-021H` §2.4 — the exchange is the source of truth; `TradingSessionState`
is a cache. When they disagree, the exchange wins, and the disagreement is
logged `WARNING` rather than silently overwritten — a repeated mismatch is a
symptom of a real bug in `EPIC-021G`'s own bookkeeping, not routine noise.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.application.services.trading_session_state import (
    TradingSessionState,
)

logger = logging.getLogger("App.LiveTradingCoordinator")


def reconcile_position_state(
    session_state: TradingSessionState, symbol: str, has_position: bool
) -> None:
    """@brief Corrects `session_state.known_open_symbols` for `symbol` to
    match `has_position` (what the exchange just reported), logging
    `WARNING` only when this app's prior belief disagreed."""
    was_known_open = symbol in session_state.known_open_symbols
    if was_known_open != has_position:
        logger.warning(
            "Position state mismatch for %s: app believed %s, exchange "
            "reports %s — exchange wins.",
            symbol,
            "open" if was_known_open else "flat",
            "open" if has_position else "flat",
        )

    if has_position:
        session_state.known_open_symbols.add(symbol)
    else:
        session_state.known_open_symbols.discard(symbol)
