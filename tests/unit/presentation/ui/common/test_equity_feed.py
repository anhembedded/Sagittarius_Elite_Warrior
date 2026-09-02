"""Tests for `EquityFeed` (`EPIC-021M`).

Same shape as `test_order_feed.py`: proves the one-subscriber pattern —
`EquitySampledEvent` reaches the Trading screen re-emitted intact."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.domain.events.equity_sampled_event import (
    EquitySampledEvent,
)
from Sagittarius_Elite_Warrior.src.domain.trading.equity_sample import EquitySample
from Sagittarius_Elite_Warrior.src.presentation.ui.common.equity_feed import EquityFeed
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus


def _sample() -> EquitySample:
    return EquitySample(
        captured_at=datetime(2026, 9, 2, 12, 0, tzinfo=UTC),
        wallet_balance=Decimal("1000.00"),
        unrealized_pnl=Decimal("25.50"),
    )


def _feed(qapp):
    bus = MemoryEventBus()
    feed = EquityFeed(bus)
    return bus, feed


def test_equity_sampled_event_reaches_every_listener(qapp):
    bus, feed = _feed(qapp)
    seen: list = []
    feed.equitySampled.connect(seen.append)

    event = EquitySampledEvent(sample=_sample())
    bus.emit(event)

    assert len(seen) == 1
    assert seen[0] is event


def test_stop_unsubscribes(qapp):
    bus, feed = _feed(qapp)
    seen: list = []
    feed.equitySampled.connect(seen.append)

    feed.stop()
    bus.emit(EquitySampledEvent(sample=_sample()))

    assert seen == []
