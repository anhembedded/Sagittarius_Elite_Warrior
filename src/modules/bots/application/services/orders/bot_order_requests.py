"""`EPIC-029E` - the orders one bot asks trading for, as requests (ADR D1, D5).

Split from `bot_order_gateway.py` (the 400-line ceiling): the gateway sends and classifies, this
builds. Every request carries the bot's owner id (the lease) and its tag (`SEW-{tag}-...`, D5), so
trading counts it against the bot's budget.

Two kinds, by what trading does with them (`BUG-241`):

  - a **placement** (a ladder level, an opening slice) is judged by the whole owner budget and
    waits its turn on the pacer;
  - an **exit** (a Spot sale of the base, a Futures reduce-only close) is sent as
    `OrderPurpose.CLOSE`: trading judges it by the inventory or the exposure and not by the
    open-order count, the spacing or the rate that pace placements, and the book still counts it.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_identity import (
    BotIdentity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_purpose import (
    OrderPurpose,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    OrderRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.time_in_force import (
    TimeInForce,
)


class BotOrderRequests:
    """Builds the requests of one bot."""

    def __init__(self, identity: BotIdentity) -> None:
        self._identity = identity

    def limit(
        self,
        side: OrderSide,
        price: Decimal,
        quantity: Decimal,
        *,
        reduce_only: bool = False,
    ) -> OrderRequest:
        """A placement: a LIMIT GTC order at `price`."""
        return self._request(
            side,
            OrderType.LIMIT,
            quantity,
            price,
            TimeInForce.GTC,
            reduce_only=reduce_only,
        )

    def market(
        self, side: OrderSide, quantity: Decimal, reference_price: Decimal
    ) -> OrderRequest:
        """A placement: a market order of `quantity` base."""
        return self._request(side, OrderType.MARKET, quantity, reference_price)

    def market_buy_for_quote(
        self, quote: Decimal, reference_price: Decimal
    ) -> OrderRequest:
        """A placement: a market BUY spending `quote` (Spot `quoteOrderQty`)."""
        return OrderRequest(
            symbol=self._identity.symbol,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=quote / reference_price,
            reference_price=reference_price,
            owner_id=self._identity.owner_id,
            quote_quantity=quote,
            client_order_tag=self._identity.tag,
        )

    def exit(
        self,
        side: OrderSide,
        quantity: Decimal,
        reference_price: Decimal,
        *,
        reduce_only: bool = False,
    ) -> OrderRequest:
        """An exit slice: a market order sent as a close. On a position venue it is reduce-only
        (the exchange refuses it when it would grow or flip the position, which makes a close safe
        to send twice); on Spot it is a SELL of the base the bot holds."""
        return self._request(
            side,
            OrderType.MARKET,
            quantity,
            reference_price,
            reduce_only=reduce_only,
            purpose=OrderPurpose.CLOSE,
        )

    def _request(
        self,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Decimal,
        time_in_force: TimeInForce | None = None,
        *,
        reduce_only: bool = False,
        purpose: OrderPurpose = OrderPurpose.ENTRY,
    ) -> OrderRequest:
        return OrderRequest(
            symbol=self._identity.symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            reference_price=price,
            reduce_only=reduce_only,
            purpose=purpose,
            owner_id=self._identity.owner_id,
            time_in_force=time_in_force,
            client_order_tag=self._identity.tag,
        )
