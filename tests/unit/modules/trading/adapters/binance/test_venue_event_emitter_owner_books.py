"""`EPIC-029` ADR D6 — the venue's emission path updates the owner book
**before** the event reaches the bus.

@details The bus is the Engine's real `MemoryEventBus`, which calls each
subscriber synchronously inside `emit`, so a subscriber sees exactly the
state the book was in when the event was published. The last test is the
acceptance criterion's own: a subscriber that places the counter SELL inside
its handler, through the real `ExecuteOrderCommandHandler`, is accepted.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.venue_event_emitter import (
    VenueEventEmitter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.command import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_book import (
    OwnerBook,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_books import (
    OwnerBooks,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_ended_event import (
    OrderEndedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    EMPTY_INVENTORY,
    OwnerBudget,
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistration,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.orders.execute_order_builders import (
    make_handler,
    order_request,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus

_TAG = "a3f9c1"
_NOW = datetime(2026, 10, 3, 12, tzinfo=UTC)
_REGISTRATION = OwnerBudgetRegistration(
    owner_id="bot-1",
    tag=_TAG,
    symbol="BTCUSDT",
    run_started_at=datetime(2026, 10, 1, tzinfo=UTC),
    budget=OwnerBudget(10, Decimal(5000), timedelta(0), 60, timedelta(minutes=1)),
)


def _buy(status: OrderStatus = OrderStatus.FILLED) -> Order:
    return Order(
        client_order_id=ClientOrderId(f"SEW-{_TAG}-0000000001"),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.002"),
        status=status,
        price=Decimal(60000),
    )


def _wired(books: OwnerBooks) -> tuple[VenueEventEmitter, MemoryEventBus]:
    bus = MemoryEventBus()
    return VenueEventEmitter(bus, TradingVenue.SPOT_TESTNET, books), bus


def test_a_subscriber_sees_the_fill_already_in_the_book() -> None:
    books = OwnerBooks()
    books.install(_TAG, OwnerBook(_REGISTRATION, EMPTY_INVENTORY))
    emitter, bus = _wired(books)
    seen: list[OwnerInventory] = []
    bus.on(OrderFilledEvent, lambda _event: seen.append(books.shares()[0].inventory))

    emitter.order_filled(_buy(), (Decimal(60000), Decimal("0.002")), None)

    assert seen == [OwnerInventory(Decimal("0.002"), Decimal(120))]


def test_a_subscriber_sees_an_ended_order_already_released() -> None:
    books = OwnerBooks()
    books.install(_TAG, OwnerBook(_REGISTRATION, EMPTY_INVENTORY))
    books.record_sent(_TAG, _buy(OrderStatus.NEW), Decimal(120), _NOW)
    emitter, bus = _wired(books)
    open_counts: list[int] = []
    bus.on(
        OrderEndedEvent,
        lambda _event: open_counts.append(
            books.facts(_TAG, "bot-1", _buy(), _NOW).open_order_count  # type: ignore[union-attr]
        ),
    )

    emitter.order_ended(_buy(OrderStatus.CANCELED))

    assert open_counts == [0]


def test_a_counter_sell_placed_inside_the_fill_handler_is_accepted() -> None:
    """Before the fill the bot holds nothing, so its SELL would be refused
    by the inventory check; the book is updated first, so it is not."""
    raw_client = Mock()
    raw_client.futures_create_order.return_value = {}
    handler, state = make_handler(raw_client=raw_client)
    state.install_owner_book(
        _TAG,
        OwnerBook(_REGISTRATION, EMPTY_INVENTORY),
        expected_switch_epoch=state.switch_epoch,
    )
    emitter, bus = _wired(state.owner_books)
    counter_sell = ExecuteOrderCommand(
        order_request=order_request(
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.002"),
            reference_price=Decimal(60600),
            client_order_tag=_TAG,
        ),
        live=True,
        owner_id="bot-1",
    )
    answers: list[object] = []
    bus.on(
        OrderFilledEvent, lambda _event: answers.append(handler.execute(counter_sell))
    )

    emitter.order_filled(_buy(), (Decimal(60000), Decimal("0.002")), None)

    assert [answer.blocked_by for answer in answers] == [None]  # type: ignore[attr-defined]
