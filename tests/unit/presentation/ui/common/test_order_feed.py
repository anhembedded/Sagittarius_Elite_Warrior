"""Tests for `OrderFeed` (`EPIC-021H`).

Proves the one-subscriber shape: `OrderFilledEvent`/`PositionChangedEvent`
reach every listening screen through exactly this Feed, re-emitted intact
rather than dropped or reshaped."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.domain.events.live_order_blocked_event import (
    LiveOrderBlockedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.position_changed_event import (
    PositionChangedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.position_closed_event import (
    PositionClosedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.trading.client_order_id import ClientOrderId
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
from Sagittarius_Elite_Warrior.src.presentation.ui.common.order_feed import OrderFeed
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus


def _order() -> Order:
    return Order(
        client_order_id=ClientOrderId("SEW-a91f4c72e0b8"),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.002"),
    )


def _position() -> LivePosition:
    return LivePosition(
        symbol="BTCUSDT",
        position_amt=Decimal("0.002"),
        entry_price=Decimal("64105.35"),
        mark_price=Decimal("64105.35"),
        unrealized_pnl=Decimal("-0.02"),
        leverage=10,
        margin_type=MarginType.CROSSED,
        liquidation_price=LiquidationPrice(Decimal(50000)),
        updated_at=datetime(2026, 8, 27, tzinfo=UTC),
    )


def _feed(qapp):
    bus = MemoryEventBus()
    feed = OrderFeed(bus)
    return bus, feed


def test_order_filled_event_reaches_every_listener(qapp):
    bus, feed = _feed(qapp)
    seen: list = []
    feed.orderFilled.connect(seen.append)

    event = OrderFilledEvent(
        order=_order(), fill_price=Decimal("64105.10"), fill_quantity=Decimal("0.001")
    )
    bus.emit(event)

    assert len(seen) == 1
    assert seen[0] is event


def test_position_changed_event_reaches_every_listener(qapp):
    bus, feed = _feed(qapp)
    seen: list = []
    feed.positionChanged.connect(seen.append)

    event = PositionChangedEvent(position=_position())
    bus.emit(event)

    assert len(seen) == 1
    assert seen[0] is event


def test_position_closed_event_reaches_every_listener(qapp):
    bus, feed = _feed(qapp)
    seen: list = []
    feed.positionClosed.connect(seen.append)

    event = PositionClosedEvent(symbol="BTCUSDT")
    bus.emit(event)

    assert len(seen) == 1
    assert seen[0] is event


def test_live_order_blocked_event_reaches_every_listener(qapp):
    """`BUG-084` — a signal-driven live order blocked by sizing or a
    trading limit must reach the Trading screen through this same Feed,
    not stay a log-only fact."""
    bus, feed = _feed(qapp)
    seen: list = []
    feed.orderBlocked.connect(seen.append)

    event = LiveOrderBlockedEvent(symbol="BTCUSDT", reason="max_notional_per_order")
    bus.emit(event)

    assert len(seen) == 1
    assert seen[0] is event


def test_stop_unsubscribes_all_four(qapp):
    bus, feed = _feed(qapp)
    filled: list = []
    changed: list = []
    closed: list = []
    blocked: list = []
    feed.orderFilled.connect(filled.append)
    feed.positionChanged.connect(changed.append)
    feed.positionClosed.connect(closed.append)
    feed.orderBlocked.connect(blocked.append)

    feed.stop()
    bus.emit(
        OrderFilledEvent(
            order=_order(),
            fill_price=Decimal("64105.10"),
            fill_quantity=Decimal("0.001"),
        )
    )
    bus.emit(PositionChangedEvent(position=_position()))
    bus.emit(PositionClosedEvent(symbol="BTCUSDT"))
    bus.emit(LiveOrderBlockedEvent(symbol="BTCUSDT", reason="max_notional_per_order"))

    assert filled == []
    assert changed == []
    assert closed == []
    assert blocked == []
