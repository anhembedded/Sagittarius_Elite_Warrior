"""`EPIC-039L` — which protective stops a Grid's plan asks for, and which a position needs.

@details Pure rules of decisions D4 and D9, split from the service that acts on them. A LONG
grid has a SELL stop at its stop-loss price, a SHORT grid a BUY stop at its stop-loss price; a
NEUTRAL grid has both (its stop loss under the range, its take profit over it, which is the
exit it has above). The stop on the side no position covers is placed only once the owner has
recorded that the exchange does nothing with it (check T3), because a close-all order that
could open a position is the hazard of `EPIC-026K`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide

#: Whether a close-all order on the side with no position is known to do nothing (check T3 of
#: `DECISION_2026-10-16`, on Futures testnet). `False` until the owner has recorded it: then a
#: NEUTRAL grid stands only the stop that covers its position. Flipping it is a reviewed change.
NEUTRAL_BOTH_SIDES_VERIFIED = False


@dataclass(frozen=True, slots=True)
class WantedStop:
    """A stop the plan asks for: which side it closes and where it triggers."""

    side: OrderSide
    trigger_price: Decimal


def wanted_stops(params: GridParams) -> tuple[WantedStop, ...]:
    """The stops the plan asks for; none when it has no stop-loss price."""
    if params.direction is TradeDirection.NEUTRAL:
        # A NEUTRAL grid has no stop loss over the range: its exit above is the take
        # profit (`GridReason.TAKE_PROFIT`), so the short side's stop stands there.
        return tuple(
            WantedStop(side, price)
            for side, price in (
                (OrderSide.SELL, params.stop_loss_price),
                (OrderSide.BUY, params.take_profit_price),
            )
            if price is not None
        )
    price = params.stop_loss_price
    if price is None:
        return ()
    side = OrderSide.BUY if params.direction is TradeDirection.SHORT else OrderSide.SELL
    return (WantedStop(side, price),)


def covers(params: GridParams, side: OrderSide, position: Decimal) -> bool:
    """Whether a stop of `side` closes `position` (SELL a long, BUY a short); a NEUTRAL
    grid's other side waits for check T3."""
    if params.direction is TradeDirection.NEUTRAL and NEUTRAL_BOTH_SIDES_VERIFIED:
        return True
    return position > 0 if side is OrderSide.SELL else position < 0
