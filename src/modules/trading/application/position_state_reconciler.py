"""`EPIC-021H` §2.4 — the exchange is the source of truth; `TradingSessionState`
is a cache. When they disagree, the exchange wins, and the disagreement is
logged `WARNING` rather than silently overwritten — a repeated mismatch is a
symptom of a real bug in `EPIC-021G`'s own bookkeeping, not routine noise.

The exception is a symbol a budgeted owner trades (`BUG-203`): the owner's orders never
mark it open, so the session learns the owner's position only from the exchange and the
correction is logged at `DEBUG`. The owner's own divergence is confirmed, and warned about,
by the owner's watch. So is the flat report that follows the owner's close: the stop clears
the owner's book before it arrives (`BUG-233`).
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
    `WARNING` only when this app's prior belief disagreed on a symbol no
    budgeted owner trades (on one, the session was only learning it: `DEBUG`) and
    was not the flat report after a budgeted owner closed and left (`DEBUG`).

    @details `BUG-088` — the actual mutation is `session_state`'s own
    lock-guarded `reconcile_position()`: this function runs on
    `FuturesUserDataStream`'s websocket thread, a third, genuinely
    concurrent writer alongside the `ExecuteOrderCommand`/
    `EnsureSessionReadyCommand`/`EmergencyStopCommand` pool workers, so it must
    never touch `known_open_symbols` directly.
    """
    owner_left = not has_position and session_state.owner_books.take_departure(symbol)
    disagreed = session_state.reconcile_position(symbol, has_position=has_position)
    if disagreed and session_state.owner_books.has_owner_on(symbol):
        # `BUG-203` - a budgeted owner's order never marks the symbol open (`ExecuteOrderHandler`),
        # so the exchange's first report of the owner's own position is how the session learns
        # it: a fact being learned, not a belief that was wrong.
        logger.debug(
            "Position state for %s learned from the exchange: %s (a budgeted owner trades it)",
            symbol,
            "open" if has_position else "flat",
        )
    elif disagreed and owner_left:
        # `BUG-233` - the owner's stop closed the position and cleared its book before this
        # flat report arrived: the end of what the session learned from the exchange.
        logger.debug(
            "Position state for %s is flat: the budgeted owner that traded it closed and left",
            symbol,
        )
    elif disagreed:
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
    when flat), logging once per cause at `DEBUG` (a snapshot, until the owner's re-read confirms it).

    @details The exchange wins and the disagreement is reported, never
    "fixed" by trusting the bot's record and never written over the book: the
    caller publishes the divergences it gets back for the guard (`EPIC-039F`).
    Like `reconcile_position_state`, it runs on the websocket thread; the
    comparison itself is `OwnerBooks`' own lock-guarded `cross_check`.
    """
    divergences = session_state.owner_books.cross_check(symbol, exchange_quantity)
    for divergence in divergences:
        # `BUG-203` - DEBUG, not WARNING: the report can outrun the fill that explains it, so
        # this is a snapshot nobody has confirmed yet, one line per fill of a burst. The owner's
        # watch re-reads and warns itself (`GridRiskWatch`, the registration) when it persists.
        logger.debug(
            "Position %s for %s on %s: derived %s, exchange reports %s — "
            "exchange wins [position-divergence]",
            divergence.kind.value,
            divergence.tag,
            symbol,
            divergence.derived,
            divergence.exchange,
        )
    return divergences
