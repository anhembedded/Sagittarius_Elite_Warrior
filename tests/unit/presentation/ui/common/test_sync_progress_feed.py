"""Tests for `SyncProgressFeed` (`EPIC-008G` §1)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.application.events.sync_events import (
    SingleSyncProgressEvent,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.sync_progress_feed import (
    SyncProgressFeed,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus


def _feed(qapp):
    bus = MemoryEventBus()
    feed = SyncProgressFeed(bus)
    seen: list = []
    feed.progressUpdated.connect(seen.append)
    return bus, feed, seen


def test_normalises_the_event_once(qapp):
    bus, _feed_obj, seen = _feed(qapp)

    bus.emit(
        SingleSyncProgressEvent(symbol="BTCUSDT", interval="1h", current=50, total=100)
    )

    assert len(seen) == 1
    report = seen[0]
    assert (report.symbol, report.interval, report.current, report.total) == (
        "BTCUSDT",
        "1h",
        50,
        100,
    )


def test_message_has_one_source(qapp):
    """Only Data Management had progress wording before; a second screen wanting
    a line would have written a second one. Now both read this."""
    bus, _feed_obj, seen = _feed(qapp)

    bus.emit(
        SingleSyncProgressEvent(
            symbol="ETHUSDT", interval="1m", current=1234, total=5000
        )
    )

    message = seen[0].to_message()
    assert "ETHUSDT" in message and "1m" in message
    # Thousands separators are part of the shared formatting, not each caller's.
    assert "1,234" in message and "5,000" in message


def test_is_complete_needs_a_known_total(qapp):
    bus, _feed_obj, seen = _feed(qapp)

    bus.emit(SingleSyncProgressEvent(symbol="S", interval="1h", current=5, total=5))
    bus.emit(SingleSyncProgressEvent(symbol="S", interval="1h", current=5, total=0))

    assert seen[0].is_complete is True
    # total=0 means "unknown", not "instantly finished".
    assert seen[1].is_complete is False


def test_stop_unsubscribes(qapp):
    bus, feed, seen = _feed(qapp)

    feed.stop()
    bus.emit(SingleSyncProgressEvent(symbol="S", interval="1h", current=1, total=2))

    assert seen == []
