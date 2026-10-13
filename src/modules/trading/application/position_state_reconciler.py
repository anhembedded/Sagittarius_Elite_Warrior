"""`EPIC-021H` §2.4 — the exchange is the source of truth; `TradingSessionState`
is a cache. When they disagree, the exchange wins, and the disagreement is
logged `WARNING` rather than silently overwritten — a repeated mismatch is a
symptom of a real bug in `EPIC-021G`'s own bookkeeping, not routine noise.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    PositionDivergence,
)

logger = logging.getLogger("App.LiveTradingCoordinator")


def reconcile_position_state(
    session_state: TradingSessionState, symbol: str, has_position: bool
) -> None:
    """@brief Corrects `session_state.known_open_symbols` for `symbol` to
    match `has_position` (what the exchange just reported), logging
    `WARNING` only when this app's prior belief disagreed.

    @details `BUG-088` — the actual mutation is `session_state`'s own
    lock-guarded `reconcile_position()`: this function runs on
    `FuturesUserDataStream`'s websocket thread, a third, genuinely
    concurrent writer alongside the `ExecuteOrderCommand`/
    `EnsureSessionReadyCommand`/`EmergencyStopCommand` pool workers, so it must
    never touch `known_open_symbols` directly.
    """
    disagreed = session_state.reconcile_position(symbol, has_position=has_position)
    if disagreed:
        logger.warning(
            "Position state mismatch for %s: app believed %s, exchange "
            "reports %s — exchange wins.",
            symbol,
            "flat" if has_position else "open",
            "open" if has_position else "flat",
        )


def cross_check_owner_positions(
    session_state: TradingSessionState, symbol: str, exchange_quantity: Decimal
) -> tuple[PositionDivergence, ...]:
    """@brief `EPIC-039D` - compares every Futures owner's derived position on
    `symbol` with `exchange_quantity` (`positionRisk`'s signed amount, zero
    when flat), logging `WARNING` once per cause.

    @details The exchange wins and the disagreement is reported, never
    "fixed" by trusting the bot's record and never written over the book: the
    caller publishes the divergences it gets back for the guard (`EPIC-039F`).
    Like `reconcile_position_state`, it runs on the websocket thread; the
    comparison itself is `OwnerBooks`' own lock-guarded `cross_check`.
    """
    divergences = session_state.owner_books.cross_check(symbol, exchange_quantity)
    for divergence in divergences:
        logger.warning(
            "Position %s for %s on %s: derived %s, exchange reports %s — "
            "exchange wins [position-divergence]",
            divergence.kind.value,
            divergence.tag,
            symbol,
            divergence.derived,
            divergence.exchange,
        )
    return divergences
