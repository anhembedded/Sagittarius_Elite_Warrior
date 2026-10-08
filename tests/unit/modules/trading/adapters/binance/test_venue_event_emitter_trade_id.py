"""`EPIC-035P` — the fill event the venue publishes names the exchange's trade."""

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
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.adapters.binance.emitter_builder import (
    venue_emitter,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus

_ORDER = Order(
    ClientOrderId("SEW-a3f9c1-0000000001"),
    "BTCUSDT",
    OrderSide.BUY,
    OrderType.LIMIT,
    Decimal("0.002"),
    price=Decimal(60000),
)


def _published(trade_id: int | None) -> OrderFilledEvent:
    bus = MemoryEventBus()
    seen: list[OrderFilledEvent] = []
    bus.on(OrderFilledEvent, seen.append)
    emitter = venue_emitter(bus, TradingVenue.SPOT_TESTNET)

    emitter.order_filled(_ORDER, (Decimal(60000), Decimal("0.001")), None, trade_id)

    [event] = seen
    return event


def test_a_spot_fill_event_carries_the_trade_id_the_stream_reported() -> None:
    assert _published(4711).trade_id == 4711


def test_a_fill_event_of_a_venue_with_no_trade_id_carries_none() -> None:
    assert _published(None).trade_id is None
