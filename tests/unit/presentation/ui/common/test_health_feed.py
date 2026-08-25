"""Tests for `HealthFeed` (`EPIC-008G` §1).

Two things are being proved: that one subscriber replaces the three formatters
two screens used to carry, and that the request/response pair from `EPIC-008E`
removes the need for a screen to fabricate its own `HealthUpdatedEvent`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.common.health_feed import HealthFeed
from sagittarius_engine.extensions.health.health_check_requested import (
    HealthCheckRequested,
)
from sagittarius_engine.extensions.health.health_updated_event import HealthUpdatedEvent
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus

_STATUS = {
    "status": "healthy",
    "components": {"database": "ok", "event_bus": "ok", "container": "ok"},
}


def _feed(qapp):
    bus = MemoryEventBus()
    feed = HealthFeed(bus)
    seen: list = []
    feed.healthUpdated.connect(seen.append)
    return bus, feed, seen


def test_normalises_the_raw_status_dict_once(qapp):
    bus, _feed_obj, seen = _feed(qapp)

    bus.emit(HealthUpdatedEvent.event_name, HealthUpdatedEvent(_STATUS))

    assert len(seen) == 1
    report = seen[0]
    assert report.status == "HEALTHY"
    assert report.components == {
        "database": "OK",
        "event_bus": "OK",
        "container": "OK",
    }


def test_no_component_is_dropped(qapp):
    """Backtest's own formatter listed only `database` and `event_bus`, so
    `container` silently vanished from that screen. Selecting keys by hand is
    what caused it; the feed keeps whatever the engine reported."""
    bus, _feed_obj, seen = _feed(qapp)

    bus.emit(
        HealthUpdatedEvent.event_name,
        HealthUpdatedEvent(
            {"status": "degraded", "components": {"database": "down", "cache": "ok"}}
        ),
    )

    assert set(seen[0].components) == {"database", "cache"}
    assert seen[0].status == "DEGRADED"


def test_one_log_line_for_every_screen(qapp):
    """The two screens printed two different strings for one fact. Now there is
    one renderer, so there is one string."""
    bus, _feed_obj, seen = _feed(qapp)

    bus.emit(HealthUpdatedEvent.event_name, HealthUpdatedEvent(_STATUS))

    line = seen[0].to_log_line()
    assert line.startswith("[Health] Trạng thái hệ thống: HEALTHY (")
    assert "Container: OK" in line


def test_request_refresh_publishes_a_request(qapp):
    """`EPIC-008E`'s request half. A screen calls this instead of resolving
    `HealthCheckQuery` and fabricating an event, which is what both screens
    used to do."""
    bus, feed, _seen = _feed(qapp)
    requests: list = []
    bus.on(HealthCheckRequested.event_name, requests.append)

    feed.request_refresh()

    assert len(requests) == 1


def test_request_refresh_is_answered_over_the_normal_path(qapp):
    """End-to-end shape: request goes out, a responder publishes
    `HealthUpdatedEvent`, and the screen hears it on the one signal it already
    listens to — no second code path for "initial" health."""
    bus, feed, seen = _feed(qapp)
    bus.on(
        HealthCheckRequested.event_name,
        lambda _e: bus.emit(HealthUpdatedEvent.event_name, HealthUpdatedEvent(_STATUS)),
    )

    feed.request_refresh()

    assert len(seen) == 1
    assert seen[0].status == "HEALTHY"


def test_missing_or_malformed_status_does_not_raise(qapp):
    """Health reporting must never be the thing that breaks a screen."""
    bus, _feed_obj, seen = _feed(qapp)

    bus.emit(HealthUpdatedEvent.event_name, HealthUpdatedEvent({}))

    assert seen[0].status == "UNKNOWN"
    assert seen[0].components == {}


def test_stop_unsubscribes(qapp):
    bus, feed, seen = _feed(qapp)

    feed.stop()
    bus.emit(HealthUpdatedEvent.event_name, HealthUpdatedEvent(_STATUS))

    assert seen == []
