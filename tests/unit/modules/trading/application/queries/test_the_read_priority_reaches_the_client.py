"""`BOT-226` — the priority a port's caller names reaches the session that sends the request.

@details Two hops, each tested where it lives. The port's service puts the priority on the query
(`AccountSnapshotService`, `AccountActivityService`, `OrderEntryTermsService`). The query's handler
opens `prioritised(...)` around the one client call (`GetOpenPositions`, `GetOpenOrders`,
`GetMarkPrice`), so `ExchangeCallPolicy` finds it with `current_priority()` below `ITradingClient`.
The clients here record `current_priority()` at the instant they are called, as the policy reads
it; and the scope is closed again when the read returns.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.account.account_activity_service import (
    AccountActivityService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.account.account_snapshot_service import (
    AccountSnapshotService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.order_entry_terms_service import (
    OrderEntryTermsService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_mark_price import (
    GetMarkPriceQuery,
    GetMarkPriceQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_open_orders import (
    GetOpenOrdersQuery,
    GetOpenOrdersQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_open_positions import (
    GetOpenPositionsQuery,
    GetOpenPositionsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_mark_price_reader import (
    IMarkPriceReader,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.mark_price import (
    MarkPrice,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.request_priority import (
    RequestPriority,
    current_priority,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
    fake_venue_context,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_VENUE = TradingVenue.FUTURES_TESTNET
_BOTH = pytest.mark.parametrize(
    "priority", [RequestPriority.ROUTINE, RequestPriority.EXIT_GUARD]
)


class _RecordingClient(ITradingClient):
    def __init__(self) -> None:
        self.seen: list[RequestPriority] = []

    def place_order(self, order: Order) -> Order:
        raise AssertionError("a read never places")

    def find_order(self, symbol: str, client_order_id: str) -> Order | None:
        raise AssertionError("not part of this read")

    def cancel_order(self, symbol: str, client_order_id: str) -> Order:
        raise AssertionError("a read never cancels")

    def cancel_all_orders(self, symbol: str) -> list[Order]:
        raise AssertionError("a read never cancels")

    def cancel_regular_orders(self, symbol: str) -> list[Order]:
        raise AssertionError("a read never cancels")

    def cancel_conditional_orders(self, symbol: str) -> list[Order]:
        raise AssertionError("a read never cancels")

    def get_open_orders(self, symbol: str | None = None) -> list[Order]:
        self.seen.append(current_priority())
        return []

    def get_positions(self, symbol: str | None = None) -> list[LivePosition]:
        self.seen.append(current_priority())
        return []


class _Factory(ITradingClientFactory):
    def __init__(self, client: ITradingClient) -> None:
        self._client = client

    def accepted_order_types(self) -> frozenset[OrderType]:
        return frozenset({OrderType.MARKET, OrderType.LIMIT})

    def create(self, mode: OrderSubmissionMode) -> ITradingClient:
        return self._client


class _RecordingMarks(IMarkPriceReader):
    def __init__(self) -> None:
        self.seen: list[RequestPriority] = []

    def mark_price(self, symbol: str) -> MarkPrice:
        self.seen.append(current_priority())
        return MarkPrice(symbol, Decimal(100), datetime.now(UTC))


class _CapturingDispatcher(ICommandDispatcher):
    def __init__(self, answer: object) -> None:
        self.answer = answer
        self.queries: list[object] = []

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        self.queries.append(input_dto)
        return self.answer


def _contexts(client: ITradingClient, marks: IMarkPriceReader | None = None):
    return FakeVenueContexts(
        replace(
            fake_venue_context(_VENUE),
            client_factory=_Factory(client),
            mark_price_reader=marks,
        )
    )


@_BOTH
def test_the_open_positions_read_reaches_the_client_with_its_priority(
    priority: RequestPriority,
) -> None:
    client = _RecordingClient()

    GetOpenPositionsQueryHandler(_contexts(client)).execute(
        GetOpenPositionsQuery(venue=_VENUE, priority=priority)
    )

    assert client.seen == [priority]


@_BOTH
def test_the_open_orders_read_reaches_the_client_with_its_priority(
    priority: RequestPriority,
) -> None:
    client = _RecordingClient()

    GetOpenOrdersQueryHandler(_contexts(client)).execute(
        GetOpenOrdersQuery(venue=_VENUE, symbol="BTCUSDT", priority=priority)
    )

    assert client.seen == [priority]


@_BOTH
def test_the_mark_price_read_reaches_the_reader_with_its_priority(
    priority: RequestPriority,
) -> None:
    marks = _RecordingMarks()

    GetMarkPriceQueryHandler(_contexts(_RecordingClient(), marks)).execute(
        GetMarkPriceQuery(venue=_VENUE, symbol="BTCUSDT", priority=priority)
    )

    assert marks.seen == [priority]


def test_a_query_that_names_no_priority_is_routine() -> None:
    assert GetOpenPositionsQuery(venue=_VENUE).priority is RequestPriority.ROUTINE
    assert GetOpenOrdersQuery(venue=_VENUE).priority is RequestPriority.ROUTINE
    assert (
        GetMarkPriceQuery(venue=_VENUE, symbol="BTCUSDT").priority
        is RequestPriority.ROUTINE
    )


def test_the_scope_closes_with_the_read_so_the_next_request_is_routine() -> None:
    client = _RecordingClient()
    handler = GetOpenPositionsQueryHandler(_contexts(client))

    handler.execute(
        GetOpenPositionsQuery(venue=_VENUE, priority=RequestPriority.EXIT_GUARD)
    )

    assert current_priority() is RequestPriority.ROUTINE


def test_the_scope_closes_when_the_read_fails() -> None:
    class _Failing(_RecordingClient):
        def get_positions(self, symbol: str | None = None) -> list[LivePosition]:
            raise ConnectionError("no answer")

    handler = GetOpenPositionsQueryHandler(_contexts(_Failing()))

    with pytest.raises(ConnectionError):
        handler.execute(
            GetOpenPositionsQuery(venue=_VENUE, priority=RequestPriority.EXIT_GUARD)
        )

    assert current_priority() is RequestPriority.ROUTINE


@_BOTH
def test_the_ports_put_the_callers_priority_on_the_query(
    priority: RequestPriority,
) -> None:
    positions = _CapturingDispatcher(())
    orders = _CapturingDispatcher(())
    marks = _CapturingDispatcher(MarkPrice("BTCUSDT", Decimal(100), datetime.now(UTC)))

    AccountSnapshotService(positions, _VENUE).open_positions(priority)
    AccountActivityService(orders, _VENUE).open_orders("BTCUSDT", priority)
    OrderEntryTermsService(marks, _VENUE).mark_price_for("BTCUSDT", priority)

    assert [q.priority for q in positions.queries + orders.queries + marks.queries] == [
        priority,
        priority,
        priority,
    ]
