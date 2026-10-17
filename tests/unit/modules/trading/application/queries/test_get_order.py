"""`EPIC-039L` — `GetOrderQueryHandler` reads one order of the addressed venue by its client id.

@details The client is a small subclass of trading's own port: it answers for the ids the test
holds and records what it was asked. The service test beside it shows the query is addressed.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_order import (
    GetOrderQuery,
    GetOrderQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client import (
    ITradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client_factory import (
    ITradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
    fake_venue_context,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_FUTURES = TradingVenue.FUTURES_TESTNET


def _stop(cid: str, status: OrderStatus) -> Order:
    return Order(
        client_order_id=ClientOrderId(cid),
        symbol="BTCUSDT",
        side=OrderSide.SELL,
        order_type=OrderType.STOP_MARKET,
        quantity=Decimal(0),
        stop_price=Decimal(50000),
        close_position=True,
        status=status,
    )


class _FindingClient(ITradingClient):
    def __init__(self, *orders: Order) -> None:
        self._orders = orders
        self.asked: list[tuple[str, str]] = []

    def place_order(self, order: Order) -> Order:
        raise AssertionError("a read never places")

    def find_order(self, symbol: str, client_order_id: str) -> Order | None:
        self.asked.append((symbol, client_order_id))
        return next(
            (o for o in self._orders if o.client_order_id == client_order_id), None
        )

    def cancel_order(self, symbol: str, client_order_id: str) -> Order:
        raise AssertionError("a read never cancels")

    def cancel_all_orders(self, symbol: str) -> list[Order]:
        raise AssertionError("a read never cancels")

    def cancel_regular_orders(self, symbol: str) -> list[Order]:
        raise AssertionError("a read never cancels")

    def cancel_conditional_orders(self, symbol: str) -> list[Order]:
        raise AssertionError("a read never cancels")

    def get_open_orders(self, symbol: str | None = None) -> list[Order]:
        raise AssertionError("not part of this read")

    def get_positions(self, symbol: str | None = None) -> list[LivePosition]:
        raise AssertionError("not part of this read")


class _Factory(ITradingClientFactory):
    def __init__(self, client: ITradingClient) -> None:
        self._client = client

    def accepted_order_types(self) -> frozenset[OrderType]:
        return frozenset({OrderType.MARKET, OrderType.LIMIT})

    def create(self, mode: OrderSubmissionMode) -> ITradingClient:
        return self._client


def _handler(client: _FindingClient) -> GetOrderQueryHandler:
    return GetOrderQueryHandler(
        FakeVenueContexts(
            replace(fake_venue_context(_FUTURES), client_factory=_Factory(client))
        )
    )


def test_the_order_is_asked_of_the_exchange_by_symbol_and_client_id() -> None:
    client = _FindingClient(_stop("SEW-f1", OrderStatus.EXPIRED))

    order = _handler(client).execute(
        GetOrderQuery(venue=_FUTURES, symbol="BTCUSDT", client_order_id="SEW-f1")
    )

    assert order is not None
    assert order.status is OrderStatus.EXPIRED
    assert client.asked == [("BTCUSDT", "SEW-f1")]


def test_an_order_the_exchange_does_not_hold_reads_as_none() -> None:
    client = _FindingClient(_stop("SEW-f1", OrderStatus.NEW))

    order = _handler(client).execute(
        GetOrderQuery(venue=_FUTURES, symbol="BTCUSDT", client_order_id="SEW-other")
    )

    assert order is None
