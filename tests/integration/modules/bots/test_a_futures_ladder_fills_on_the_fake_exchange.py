"""`EPIC-039C` - a Futures ladder, end to end, on the fake exchange.

@details The first consumer of the fake Futures matcher: the composed app over the Futures
testnet, orders sent through its real order client, the price moved on the fake, the fills
read back both ways the app learns of them - the REST reads (`openOrders`, `positionRisk`)
and the user-data stream's own handler fed from the fake's queue. `EPIC-039D` and `039H`
build on this; nothing here mocks a port.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.time_in_force import (
    TimeInForce,
)
from sagittarius_engine.interfaces.i_event_bus import IEventBus

from .futures_fake_exchange import SYMBOL, BootedFutures, booted_futures
from .grid_fake_exchange import FakeExchange


def _limit(
    app: BootedFutures, cid: str, side: OrderSide, price: str, qty: str, **options: bool
) -> Order:
    return app.client().place_order(
        Order(
            client_order_id=ClientOrderId(cid),
            symbol=SYMBOL,
            side=side,
            order_type=OrderType.LIMIT,
            quantity=Decimal(qty),
            price=Decimal(price),
            time_in_force=TimeInForce.GTC,
            **options,
        )
    )


def test_a_resting_buy_fills_on_a_price_cross_and_the_app_hears_of_it(
    futures: FakeExchange,
) -> None:
    with booted_futures(futures) as app:
        fills: list[OrderFilledEvent] = []
        app.engine.context.container.resolve(IEventBus).on(
            OrderFilledEvent, fills.append
        )
        _limit(app, "SEW-f1", OrderSide.BUY, "63000.0", "0.010")
        assert [o.client_order_id for o in app.client().get_open_orders(SYMBOL)] == [
            "SEW-f1"
        ]

        app.move_price(Decimal(63500))
        assert fills == []

        app.move_price(Decimal(63000))

        assert app.client().get_open_orders(SYMBOL) == []
        (position,) = app.client().get_positions(SYMBOL)
        assert (position.symbol, position.position_amt) == (SYMBOL, Decimal("0.010"))
        (fill,) = fills
        assert (fill.order.client_order_id, fill.fill_price, fill.fill_quantity) == (
            "SEW-f1",
            Decimal("63000.0"),
            Decimal("0.010"),
        )


def test_a_reduce_only_exit_closes_the_position_the_ladder_opened(
    futures: FakeExchange,
) -> None:
    with booted_futures(futures) as app:
        _limit(app, "SEW-f2", OrderSide.BUY, "63000.0", "0.010")
        app.move_price(Decimal(63000))
        exit_order = _limit(
            app, "SEW-f3", OrderSide.SELL, "64000.0", "0.010", reduce_only=True
        )
        assert exit_order.reduce_only

        app.move_price(Decimal(64000))

        assert app.client().get_open_orders(SYMBOL) == []
        assert app.client().get_positions(SYMBOL) == []


def test_a_liquidation_reaches_the_app_as_a_fill_it_did_not_order(
    futures: FakeExchange,
) -> None:
    book = futures.urls.futures_book
    assert (
        book.change_margin_type({"symbol": SYMBOL, "marginType": "ISOLATED"})[0] == 200
    )
    assert book.change_leverage({"symbol": SYMBOL, "leverage": "10"})[0] == 200
    with booted_futures(futures) as app:
        fills: list[OrderFilledEvent] = []
        app.engine.context.container.resolve(IEventBus).on(
            OrderFilledEvent, fills.append
        )
        _limit(app, "SEW-f4", OrderSide.BUY, "64000.0", "1")
        app.move_price(Decimal(64000))
        (position,) = app.client().get_positions(SYMBOL)
        assert position.liquidation_price is not None
        fills.clear()

        app.move_price(Decimal(50000))

        assert app.client().get_positions(SYMBOL) == []
        (forced,) = fills
        assert str(forced.order.client_order_id).startswith("autoclose-")
        assert (forced.order.side, forced.fill_quantity) == (OrderSide.SELL, Decimal(1))
