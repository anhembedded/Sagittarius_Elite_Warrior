"""`EPIC-028E` — `GetOpenOrdersQueryHandler` reads the addressed venue's live
open orders from the exchange.

@details The client and its factory are small subclasses of trading's own
ports: they answer with the orders the test gives and record the symbol they
were asked for.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_open_orders import (
    GetOpenOrdersQuery,
    GetOpenOrdersQueryHandler,
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
_SPOT = TradingVenue.SPOT_TESTNET


def _order(cid: str, symbol: str) -> Order:
    return Order(
        client_order_id=ClientOrderId(cid),
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal(1),
        price=Decimal(100),
    )


class _OpenOrdersClient(ITradingClient):
    def __init__(self, *orders: Order) -> None:
        self._orders = orders
        self.asked: list[str | None] = []

    def place_order(self, order: Order) -> Order:
        raise AssertionError("a read never places")

    def cancel_order(self, symbol: str, client_order_id: str) -> Order:
        raise AssertionError("a read never cancels")

    def cancel_all_orders(self, symbol: str) -> list[Order]:
        raise AssertionError("a read never cancels")

    def get_open_orders(self, symbol: str | None = None) -> list[Order]:
        self.asked.append(symbol)
        return [o for o in self._orders if symbol is None or o.symbol == symbol]

    def get_positions(self, symbol: str | None = None) -> list[LivePosition]:
        raise AssertionError("not part of this read")


class _Factory(ITradingClientFactory):
    def __init__(self, client: ITradingClient) -> None:
        self._client = client

    def accepted_order_types(self) -> frozenset[OrderType]:
        return frozenset({OrderType.MARKET, OrderType.LIMIT})

    def create(self, mode: OrderSubmissionMode) -> ITradingClient:
        return self._client


def _handler(
    futures: _OpenOrdersClient, spot: _OpenOrdersClient
) -> GetOpenOrdersQueryHandler:
    return GetOpenOrdersQueryHandler(
        FakeVenueContexts(
            replace(fake_venue_context(_FUTURES), client_factory=_Factory(futures)),
            replace(fake_venue_context(_SPOT), client_factory=_Factory(spot)),
        )
    )


def test_every_open_order_of_the_addressed_venue_only() -> None:
    futures = _OpenOrdersClient(_order("SEW-f1", "BTCUSDT"))
    spot = _OpenOrdersClient(_order("SEW-s1", "ETHUSDT"), _order("SEW-s2", "BTCUSDT"))

    orders = _handler(futures, spot).execute(GetOpenOrdersQuery(venue=_SPOT))

    assert [o.client_order_id for o in orders] == ["SEW-s1", "SEW-s2"]
    assert futures.asked == []
    assert spot.asked == [None]


def test_one_symbol_is_passed_through_to_the_exchange() -> None:
    futures = _OpenOrdersClient(
        _order("SEW-f1", "BTCUSDT"), _order("SEW-f2", "ETHUSDT")
    )

    orders = _handler(futures, _OpenOrdersClient()).execute(
        GetOpenOrdersQuery(venue=_FUTURES, symbol="ETHUSDT")
    )

    assert [o.client_order_id for o in orders] == ["SEW-f2"]
    assert futures.asked == ["ETHUSDT"]
