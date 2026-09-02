"""`EPIC-021E` — the four new live-trading domain events: each must inherit
`BaseEvent` and land in the engine's `EventRegistry` catalog for free (see
`BaseEvent.__init_subclass__`), the same guarantee the four pre-existing
events already rely on."""

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.domain.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.order_rejected_event import (
    OrderRejectedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.order_submitted_event import (
    OrderSubmittedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.position_changed_event import (
    PositionChangedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.trading.client_order_id import (
    generate_client_order_id,
)
from Sagittarius_Elite_Warrior.src.domain.trading.live_position import (
    LiquidationPrice,
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.domain.trading.order import Order
from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide
from sagittarius_engine.domain.base_event import BaseEvent
from sagittarius_engine.domain.event_registry import EventRegistry

_EVENT_CLASSES = (
    OrderSubmittedEvent,
    OrderFilledEvent,
    OrderRejectedEvent,
    PositionChangedEvent,
)


def _order() -> Order:
    return Order(
        client_order_id=generate_client_order_id(),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.013"),
    )


def _position() -> LivePosition:
    return LivePosition(
        symbol="BTCUSDT",
        position_amt=Decimal("0.5"),
        entry_price=Decimal(60000),
        mark_price=Decimal(60100),
        unrealized_pnl=Decimal(50),
        leverage=10,
        margin_type=MarginType.CROSSED,
        liquidation_price=LiquidationPrice(Decimal(50000)),
        updated_at=datetime(2026, 8, 27, tzinfo=UTC),
    )


def test_every_new_event_inherits_base_event() -> None:
    for event_class in _EVENT_CLASSES:
        assert issubclass(event_class, BaseEvent)


def test_every_new_event_is_in_the_engine_catalog() -> None:
    for event_class in _EVENT_CLASSES:
        entry = EventRegistry.get(event_class.event_name)
        assert entry is not None
        assert entry.event_class is event_class


def test_order_filled_event_keeps_the_name_bot_009_waits_for() -> None:
    """`EPIC-021E` §2.3: `OrderFilledEvent` is the event `BOT-009`'s Trade
    Markers Manager has been waiting for — the class name is load-bearing."""
    assert OrderFilledEvent.__name__ == "OrderFilledEvent"


def test_order_submitted_event_carries_the_order() -> None:
    order = _order()
    event = OrderSubmittedEvent(order=order)
    assert event.order is order


def test_order_filled_event_carries_fill_details() -> None:
    order = _order()
    event = OrderFilledEvent(
        order=order, fill_price=Decimal(60000), fill_quantity=Decimal("0.013")
    )
    assert event.order is order
    assert event.fill_price == Decimal(60000)
    assert event.fill_quantity == Decimal("0.013")


def test_order_rejected_event_carries_a_named_reason() -> None:
    order = _order()
    event = OrderRejectedEvent(order=order, reason="MIN_NOTIONAL")
    assert event.order is order
    assert event.reason == "MIN_NOTIONAL"


def test_position_changed_event_carries_the_position() -> None:
    position = _position()
    event = PositionChangedEvent(position=position)
    assert event.position is position


def test_new_events_compare_equal_on_payload_not_identity() -> None:
    """Guards the same `compare=False` metadata shape the pre-existing
    events rely on (`test_events_with_the_same_payload_compare_equal`) —
    two events with identical payloads must compare equal even though each
    carries a fresh, unique `_event_id`."""
    order = _order()
    assert OrderSubmittedEvent(order=order) == OrderSubmittedEvent(order=order)
