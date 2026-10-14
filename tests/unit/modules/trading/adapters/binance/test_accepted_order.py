"""`BUG-205` — `as_accepted`: the order a venue accepted, from its placement answer."""

from __future__ import annotations

import logging
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.accepted_order import (
    as_accepted,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType


def _order(quote_quantity: Decimal | None = None) -> Order:
    return Order(
        client_order_id=ClientOrderId("SEW-a91f4c72e0b8"),
        symbol="ETHUSDT",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.0022"),
        price=Decimal(2667),
        quote_quantity=quote_quantity,
    )


def test_a_differing_origqty_is_returned_and_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("App.Trading.OrderAcceptance")
    logger.addHandler(caplog.handler)
    try:
        result = as_accepted(_order(), {"origQty": "0.00210000"})
    finally:
        logger.removeHandler(caplog.handler)

    assert result.quantity == Decimal("0.0021")
    assert "[order-quantity]" in caplog.text
    assert "0.0022" in caplog.text


def test_the_same_quantity_returns_the_order_itself() -> None:
    order = _order()

    assert as_accepted(order, {"origQty": "0.00220000"}) is order


@pytest.mark.parametrize(
    "response",
    [None, "ok", [], {}, {"origQty": "not a number"}],
    ids=["none", "text", "list", "no-origqty", "unreadable-origqty"],
)
def test_an_answer_without_a_readable_quantity_leaves_the_order_as_sent(
    response: object,
) -> None:
    order = _order()

    assert as_accepted(order, response) is order


def test_a_quote_sized_order_keeps_its_estimate() -> None:
    """A quote-sized market buy's `origQty` is what the quote bought, not an
    acceptance of the estimate the order was built with."""
    order = _order(quote_quantity=Decimal(10))

    assert as_accepted(order, {"origQty": "0.0001"}) is order
