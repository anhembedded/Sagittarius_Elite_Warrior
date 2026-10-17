"""`EPIC-039L` — a Grid's record of one protective stop standing (or about to stand) on the exchange.

@details The record is the bot's own account of an order that lives on the exchange, saved
with the runtime **before** the order is sent (decision D5): `INTENDED` holds the client id
and the trigger price, and the exchange is asked by that id. It is never a safety input; the
exchange's own list of open algo orders is what a reconcile compares it with.

The record exists from `INTENDED`: `ABSENT` has none, and `ENDED` is dropped (`moved`
answers `None`).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.protective_stop_fsm_matrix import (
    ProtectiveStopEvent,
    ProtectiveStopState,
    next_protective_stop_state,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide


@dataclass(frozen=True, slots=True)
class ProtectiveStop:
    """One stop that closes the position of the bot's symbol when the mark price reaches it."""

    #: The `clientAlgoId` the exchange knows it by: `SEW-{tag}-{hex10}`.
    client_order_id: str
    #: The side of the order: SELL closes a long, BUY closes a short.
    side: OrderSide
    #: The mark price that triggers it.
    trigger_price: Decimal
    state: ProtectiveStopState = ProtectiveStopState.INTENDED

    def moved(self, event: ProtectiveStopEvent) -> ProtectiveStop | None:
        """The stop after `event`, or `None` when it is over (`ABSENT` or `ENDED`: no record).

        @raise InvalidProtectiveStopTransitionError The table declares no such transition."""
        state = next_protective_stop_state(self.state, event)
        if state in (ProtectiveStopState.ABSENT, ProtectiveStopState.ENDED):
            return None
        return replace(self, state=state)
