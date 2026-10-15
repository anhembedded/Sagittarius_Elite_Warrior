"""What a reading of one symbol's position changes in the app, whichever way it was taken.

An `ACCOUNT_UPDATE` names the symbols whose position changed. The stream reads each back through
the venue's gated client (`apply_positions`: the session's belief, then the event that says the
position moved or closed). While the exchange's pause runs that read is refused, and the payload
itself is all there is: it carries the signed amount at the event (`"pa"`) but not the mark, the
leverage or the liquidation price, so it settles the two facts that need only the amount
(`settle_from_amount`: whether the symbol holds a position, and that it closed) and leaves the
rest to the read the pause deferred (`BUG-216`).
"""

from __future__ import annotations

import logging
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.venue_event_emitter import (
    VenueEventEmitter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.position_state_reconciler import (
    reconcile_position_state,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)

logger = logging.getLogger("App.UserDataStream")


def apply_positions(
    session_state: TradingSessionState,
    events: VenueEventEmitter,
    symbol: str,
    positions: list[LivePosition],
) -> None:
    """What the exchange's reading of `symbol`'s position changes here: the session's
    belief, and the event that says the position moved or closed."""
    reconcile_position_state(session_state, symbol, has_position=bool(positions))
    if positions:
        events.position_changed(positions[0])
        # `BUG-095` - `DEBUG`: one per changed position, per `ACCOUNT_UPDATE`.
        logger.debug(
            "ACCOUNT_UPDATE  %s  pos %s  entry %s  uPnL %s",
            symbol,
            positions[0].position_amt,
            positions[0].entry_price,
            positions[0].unrealized_pnl,
        )
    else:
        # `BUG-086` - closing is a real change, carried by a dedicated event:
        # `LivePosition` forbids `position_amt == 0`, so `PositionChangedEvent` cannot.
        events.position_closed(symbol)
        logger.debug("ACCOUNT_UPDATE  %s  position closed", symbol)


def settle_from_amount(
    session_state: TradingSessionState,
    events: VenueEventEmitter,
    symbol: str,
    amount: Decimal,
) -> None:
    """What the amount alone settles while the position cannot be read: whether `symbol`
    holds a position (`known_open_symbols`) and, when it is flat, that it closed. A position
    that is open keeps the event with its mark and liquidation price for the deferred read."""
    reconcile_position_state(session_state, symbol, has_position=amount != 0)
    if amount == 0:
        events.position_closed(symbol)
    logger.debug(
        "ACCOUNT_UPDATE  %s  amount %s settled from the report; the read waits for the pause",
        symbol,
        amount,
    )
