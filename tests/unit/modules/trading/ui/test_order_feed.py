"""Tests for `OrderFeed` (`EPIC-021H`).

Proves the one-subscriber shape: `OrderFilledEvent`/`PositionChangedEvent`
reach every listening screen through exactly this Feed, re-emitted intact
rather than dropped or reshaped."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    AccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.account_summary_changed_event import (
    AccountSummaryChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.account_summary_stale_event import (
    AccountSummaryStaleEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.holdings_changed_event import (
    HoldingsChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.live_order_blocked_event import (
    LiveOrderBlockedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_ended_event import (
    OrderEndedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.position_changed_event import (
    PositionChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.position_closed_event import (
    PositionClosedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LiquidationPrice,
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_feed import OrderFeed
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
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
    feed = OrderFeed(bus, TradingVenue.FUTURES_TESTNET)
    return bus, feed


def test_order_filled_event_reaches_every_listener(qapp):
    bus, feed = _feed(qapp)
    seen: list = []
    feed.orderFilled.connect(seen.append)

    event = OrderFilledEvent(
        order=_order(),
        fill_price=Decimal("64105.10"),
        fill_quantity=Decimal("0.001"),
        venue=TradingVenue.FUTURES_TESTNET,
    )
    bus.emit(event)

    assert len(seen) == 1
    assert seen[0] is event


def test_position_changed_event_reaches_every_listener(qapp):
    bus, feed = _feed(qapp)
    seen: list = []
    feed.positionChanged.connect(seen.append)

    event = PositionChangedEvent(
        position=_position(), venue=TradingVenue.FUTURES_TESTNET
    )
    bus.emit(event)

    assert len(seen) == 1
    assert seen[0] is event


def test_position_closed_event_reaches_every_listener(qapp):
    bus, feed = _feed(qapp)
    seen: list = []
    feed.positionClosed.connect(seen.append)

    event = PositionClosedEvent(symbol="BTCUSDT", venue=TradingVenue.FUTURES_TESTNET)
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

    event = LiveOrderBlockedEvent(
        symbol="BTCUSDT",
        reason="max_notional_per_order",
        venue=TradingVenue.FUTURES_TESTNET,
    )
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
            venue=TradingVenue.FUTURES_TESTNET,
        )
    )
    bus.emit(
        PositionChangedEvent(position=_position(), venue=TradingVenue.FUTURES_TESTNET)
    )
    bus.emit(PositionClosedEvent(symbol="BTCUSDT", venue=TradingVenue.FUTURES_TESTNET))
    bus.emit(
        LiveOrderBlockedEvent(
            symbol="BTCUSDT",
            reason="max_notional_per_order",
            venue=TradingVenue.FUTURES_TESTNET,
        )
    )

    assert filled == []
    assert changed == []
    assert closed == []
    assert blocked == []


def test_another_venues_events_never_reach_this_feed(qapp):
    """`EPIC-028C` — Futures and Spot share one bus: a Spot fill, position,
    closure, holdings change or blocked order never reaches the Futures
    screen's feed."""
    bus, feed = _feed(qapp)
    seen: list = []
    for signal in (
        feed.orderFilled,
        feed.positionChanged,
        feed.positionClosed,
        feed.orderBlocked,
        feed.holdingsChanged,
    ):
        signal.connect(seen.append)
    spot = TradingVenue.SPOT_TESTNET

    bus.emit(
        OrderFilledEvent(
            order=_order(),
            fill_price=Decimal(64000),
            fill_quantity=Decimal("0.002"),
            venue=spot,
        )
    )
    bus.emit(PositionChangedEvent(position=_position(), venue=spot))
    bus.emit(PositionClosedEvent(symbol="BTCUSDT", venue=spot))
    bus.emit(LiveOrderBlockedEvent(symbol="BTCUSDT", reason="limit", venue=spot))
    bus.emit(HoldingsChangedEvent(holdings=(), venue=spot))
    qapp.processEvents()

    assert seen == []


def test_the_account_summary_of_this_venue_reaches_the_desk_and_no_other(qapp):
    """`EPIC-028J` — the summary panel's two events come through this Feed,
    filtered by venue like every other trading event."""
    bus, feed = _feed(qapp)
    changed: list = []
    stale: list = []
    feed.accountSummaryChanged.connect(changed.append)
    feed.accountSummaryStale.connect(stale.append)
    mine = AccountSummaryChangedEvent(
        summary=AccountSummary(
            venue=TradingVenue.FUTURES_TESTNET,
            available_balance=Decimal(10),
            equity=Decimal(12),
        )
    )
    spot_stale = AccountSummaryStaleEvent(
        reason="timeout", venue=TradingVenue.SPOT_TESTNET
    )
    my_stale = AccountSummaryStaleEvent(
        reason="timeout", venue=TradingVenue.FUTURES_TESTNET
    )

    bus.emit(mine)
    bus.emit(spot_stale)
    bus.emit(my_stale)
    qapp.processEvents()

    assert changed == [mine]
    assert stale == [my_stale]


def test_an_ended_order_of_this_venue_reaches_the_desk_and_no_other(qapp):
    """`EPIC-028I` — the TP/SL follower learns an entry ended unfilled
    through this Feed, filtered by venue like every other trading event."""
    bus, feed = _feed(qapp)
    ended: list = []
    feed.orderEnded.connect(ended.append)
    mine = OrderEndedEvent(order=_order(), venue=TradingVenue.FUTURES_TESTNET)

    bus.emit(OrderEndedEvent(order=_order(), venue=TradingVenue.SPOT_TESTNET))
    bus.emit(mine)
    qapp.processEvents()

    assert ended == [mine]
