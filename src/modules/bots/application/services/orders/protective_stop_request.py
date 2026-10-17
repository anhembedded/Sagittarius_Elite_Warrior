"""`EPIC-039L` — the request that places a bot's protective stop.

@details A pure function from the stop the bot saved to the `OrderRequest` trading is asked
for: a `STOP_MARKET` (or, for a take profit, `TAKE_PROFIT_MARKET`) that closes the whole
position, triggers on the **mark** price (a position is liquidated on the mark, decision D3),
carries the id the bot saved first (D5) and the protective purpose, so the limits that pace new
trades do not refuse it. `reference_price` and `last_price` are the mark the stop is judged
against: a stop already beyond it is refused before the network, by name.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_identity import (
    BotIdentity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_purpose import (
    OrderPurpose,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    OrderRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.working_type import (
    WorkingType,
)


@dataclass(frozen=True, slots=True)
class ProtectiveStopOrder:
    """One stop to place: its saved id, which side it closes, where it triggers, and the mark."""

    client_order_id: ClientOrderId
    side: OrderSide
    trigger_price: Decimal
    mark_price: Decimal


def protective_stop_request(
    stop: ProtectiveStopOrder, identity: BotIdentity
) -> OrderRequest:
    """The request for `stop`, owned by the bot `identity`."""
    return OrderRequest(
        symbol=identity.symbol,
        side=stop.side,
        order_type=OrderType.STOP_MARKET,
        quantity=Decimal(0),
        reference_price=stop.mark_price,
        owner_id=identity.owner_id,
        stop_price=stop.trigger_price,
        last_price=stop.mark_price,
        purpose=OrderPurpose.PROTECTIVE,
        client_order_tag=identity.tag,
        close_position=True,
        working_type=WorkingType.MARK_PRICE,
        client_order_id=stop.client_order_id,
    )
