"""Tests for `BaseFeed` — the landing point for `architecture-rule.md` §6.3's
promotion rule.

These exist because of §7 of that same rule: a decided-but-unbuilt extension
point must be a real type with real constraints, not a paragraph. A docstring
saying "subclasses must call `self._events`" is advice; a test that fails when
they do not is a contract.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.common.base_feed import BaseFeed
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus


class _Recording(BaseFeed):
    """Minimal well-behaved subclass: subscribes through `self._events`."""

    def __init__(self, event_bus, parent=None):
        self.seen: list[object] = []
        super().__init__(event_bus, parent)

    def _subscribe(self) -> None:
        self._events.on("demo.event", self.seen.append)


def test_a_subclass_that_forgets_subscribe_fails_at_construction(qapp):
    """The constraint `BaseFeed` exists to enforce. Without it a half-written
    Feed constructs fine and silently never receives anything — the exact
    failure mode the whole epic is about (an event with no subscriber)."""

    class _Incomplete(BaseFeed):
        pass

    with pytest.raises(NotImplementedError) as excinfo:
        _Incomplete(MemoryEventBus())

    # The message must name the offending class, or a reader gets a bare
    # NotImplementedError with no idea which Feed is broken.
    assert "_Incomplete" in str(excinfo.value)


def test_subscription_happens_during_construction(qapp):
    """A Feed is live as soon as it exists — no separate `start()` to forget."""
    bus = MemoryEventBus()
    feed = _Recording(bus)

    bus.emit("demo.event", {"n": 1})

    assert feed.seen == [{"n": 1}]


def test_stop_unsubscribes(qapp):
    bus = MemoryEventBus()
    feed = _Recording(bus)

    feed.stop()
    bus.emit("demo.event", {"n": 2})

    assert feed.seen == []


def test_stop_is_idempotent(qapp):
    feed = _Recording(MemoryEventBus())

    feed.stop()
    feed.stop()  # must not raise


def test_subclasses_get_the_main_thread_hop_without_asking(qapp):
    """`BaseFeed` wraps the bus in `QtEventBridge` itself rather than leaving it
    to each subclass. `runtime.tasks.failed` is published from a worker thread,
    and a Feed that subscribed the bus directly would deliver on that thread —
    `BUG-031`'s class of defect. Enforced structurally: a subclass only ever
    sees `self._events`, never the raw bus."""
    feed = _Recording(MemoryEventBus())

    assert not hasattr(feed, "_event_bus"), (
        "a subclass must not be handed the raw bus — it would bypass the hop"
    )
    assert hasattr(feed._events, "off_all")
