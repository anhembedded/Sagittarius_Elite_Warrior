"""`BUG-241` — which of a bot's requests are exits.

A placement is judged by the whole owner budget; an exit is sent as a close and answers to the
inventory or the exposure only. The gateway sends what this builds, so the purpose is decided in
one place.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_identity import (
    BotIdentity,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_order_requests import (
    BotOrderRequests,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_purpose import (
    OrderPurpose,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType

_REQUESTS = BotOrderRequests(BotIdentity("bot.a3f9c1", "a3f9c1", "BTCUSDT"))
_PRICE = Decimal(50000)
_QUANTITY = Decimal("0.01")


def test_a_spot_exit_is_a_market_sell_sent_as_a_close_with_the_bots_tag() -> None:
    request = _REQUESTS.exit(OrderSide.SELL, _QUANTITY, _PRICE)

    assert request.purpose is OrderPurpose.CLOSE
    assert request.order_type is OrderType.MARKET
    assert request.side is OrderSide.SELL
    assert not request.reduce_only
    assert request.client_order_tag == "a3f9c1"
    assert request.owner_id == "bot.a3f9c1"


def test_a_position_exit_is_reduce_only_and_sent_as_a_close() -> None:
    request = _REQUESTS.exit(OrderSide.BUY, _QUANTITY, _PRICE, reduce_only=True)

    assert request.purpose is OrderPurpose.CLOSE
    assert request.reduce_only


def test_a_placement_is_never_sent_as_a_close() -> None:
    placements = (
        _REQUESTS.limit(OrderSide.SELL, _PRICE, _QUANTITY, reduce_only=True),
        _REQUESTS.market(OrderSide.SELL, _QUANTITY, _PRICE),
        _REQUESTS.market_buy_for_quote(Decimal(100), _PRICE),
    )

    assert [request.purpose for request in placements] == [OrderPurpose.ENTRY] * 3
