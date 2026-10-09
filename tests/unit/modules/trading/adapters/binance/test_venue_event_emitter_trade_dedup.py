"""`BOT-173` — a trade is counted once, whichever record of it arrives first.

@details The placement response and the user-data stream both report through
the venue's one emitter. These tests drive it with the real `MemoryEventBus`
and a real owner book, in each arrival order, and assert what a consumer
sees: one `OrderFilledEvent` per trade and an inventory moved once.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.venue_event_emitter import (
    VenueEventEmitter,
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
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistration,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus

_TAG = "a3f9c1"
_FILL = (Decimal(60000), Decimal("0.002"))
_REGISTRATION = OwnerBudgetRegistration(
    owner_id="bot-1",
    tag=_TAG,
    symbol="BTCUSDT",
    run_started_at=datetime(2026, 10, 1, tzinfo=UTC),
    budget=OwnerBudget(10, Decimal(5000), timedelta(0), 60, timedelta(minutes=1)),
)


def _order(symbol: str = "BTCUSDT") -> Order:
    return Order(
        client_order_id=ClientOrderId(f"SEW-{_TAG}-0000000001"),
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.002"),
        status=OrderStatus.FILLED,
    )


class _Wired:
    def __init__(self) -> None:
        self.books = OwnerBooks()
        self.books.install(_TAG, OwnerBook(_REGISTRATION, EMPTY_INVENTORY))
        self.bus = MemoryEventBus()
        self.events: list[OrderFilledEvent] = []
        self.bus.on(OrderFilledEvent, self.events.append)
        self.emitter = VenueEventEmitter(
            self.bus, TradingVenue.SPOT_TESTNET, self.books
        )

    @property
    def held(self) -> Decimal:
        return self.books.shares()[0].inventory.quantity


@pytest.mark.parametrize("sources", ["response then stream", "stream then response"])
def test_a_trade_two_records_tell_of_is_counted_once_in_either_order(
    sources: str,
) -> None:
    world = _Wired()

    # Both records carry the same trade id; which one comes first does not matter.
    for _ in sources.split(" then "):
        world.emitter.order_filled(_order(), _FILL, None, 777)

    assert world.held == Decimal("0.002")
    assert [event.trade_id for event in world.events] == [777]


def test_two_trades_of_one_order_are_both_counted() -> None:
    world = _Wired()

    world.emitter.order_filled(_order(), _FILL, None, 777)
    world.emitter.order_filled(_order(), _FILL, None, 778)

    assert world.held == Decimal("0.004")
    assert [event.trade_id for event in world.events] == [777, 778]


def test_the_same_trade_id_on_another_symbol_is_another_trade() -> None:
    world = _Wired()

    world.emitter.order_filled(_order("BTCUSDT"), _FILL, None, 777)
    world.emitter.order_filled(_order("ETHUSDT"), _FILL, None, 777)

    assert len(world.events) == 2


def test_a_fill_without_a_trade_id_cannot_be_recognised_and_is_always_counted() -> None:
    world = _Wired()

    world.emitter.order_filled(_order(), _FILL, None, None)
    world.emitter.order_filled(_order(), _FILL, None, None)

    assert len(world.events) == 2


def test_a_trade_the_registration_already_counted_is_not_counted_again() -> None:
    """The third source: the history a registration replayed (`BUG-194`)."""
    world = _Wired()
    world.books.install(
        _TAG,
        OwnerBook(
            _REGISTRATION,
            EMPTY_INVENTORY,
            counted=lambda trade_id: trade_id == 777,
        ),
    )

    world.emitter.order_filled(_order(), _FILL, None, 777)

    assert world.held == 0
