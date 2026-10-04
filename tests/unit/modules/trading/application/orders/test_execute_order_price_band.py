"""`BUG-146` — an order priced outside the venue's `PERCENT_PRICE_BY_SIDE`
band is refused before any request, like `MIN_NOTIONAL` (`BUG-090`).

@details The band's reference is the order's `last_price`, the same market
price the stop gate reads; without one the check does not run and the
exchange stays the judge, as before. BTCUSDT's band here is 0.2 to 5 times
the price: at a last price of 64 000, buys from 12 800 to 320 000.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.command import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderPriceRejection,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.price_band_check import (
    PriceBandCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    PercentPriceBand,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.orders.execute_order_builders import (
    make_handler,
    order_request,
)

_BAND = PercentPriceBand(
    bid_down=Decimal("0.2"),
    bid_up=Decimal(5),
    ask_down=Decimal("0.2"),
    ask_up=Decimal(5),
)
_LAST = Decimal(64000)


def _limit(
    side: OrderSide, price: str, last: Decimal | None = _LAST
) -> ExecuteOrderCommand:
    return ExecuteOrderCommand(
        order_request=order_request(
            side=side,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.01"),
            reference_price=Decimal(price),
            last_price=last,
        ),
        live=True,
    )


def test_a_buy_below_the_band_is_never_sent() -> None:
    raw_client = Mock()
    handler, state = make_handler(raw_client=raw_client, price_band=_BAND)

    result = handler.execute(_limit(OrderSide.BUY, "12799.99"))

    assert result.blocked_by is ExecuteOrderPriceRejection.OUTSIDE_PRICE_BAND
    assert result.preview is not None
    assert result.preview.price_band_check is PriceBandCheck.OUTSIDE
    raw_client.futures_create_order.assert_not_called()
    assert state.orders_sent_this_session == 0


@pytest.mark.parametrize(
    ("side", "price"),
    [(OrderSide.BUY, "12800.00"), (OrderSide.SELL, "320000.00")],
    ids=["buy-at-floor", "sell-at-ceiling"],
)
def test_an_order_at_the_band_edge_is_not_refused_by_it(
    side: OrderSide, price: str
) -> None:
    handler, _ = make_handler(raw_client=Mock(), price_band=_BAND)

    result = handler.execute(_limit(side, price))

    assert result.preview is not None
    assert result.preview.price_band_check is PriceBandCheck.INSIDE
    assert result.blocked_by is not ExecuteOrderPriceRejection.OUTSIDE_PRICE_BAND


def test_a_sell_above_the_band_is_refused() -> None:
    handler, _ = make_handler(raw_client=Mock(), price_band=_BAND)

    result = handler.execute(_limit(OrderSide.SELL, "320000.01"))

    assert result.blocked_by is ExecuteOrderPriceRejection.OUTSIDE_PRICE_BAND


def test_without_a_last_price_the_band_is_not_judged() -> None:
    handler, _ = make_handler(raw_client=Mock(), price_band=_BAND)

    result = handler.execute(_limit(OrderSide.BUY, "12799.99", last=None))

    assert result.preview is not None
    assert result.preview.price_band_check is None
