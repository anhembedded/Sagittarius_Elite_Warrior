"""`EPIC-033P` stage 2 — what the Developer mode's event log is fed from.

The recorder is an Engine `IBusObserver`: it runs inside the dispatch path on
whichever thread emits, so it only appends to a bounded buffer the UI thread
drains. These tests drive it through the Engine's real bus.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from Sagittarius_Elite_Warrior.src.shell.developer_mode.bus_event_recorder import (
    BusEventRecord,
    BusEventRecorder,
)
from sagittarius_engine.infrastructure.event_bus.bus_observers import bus_observers
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import (
    MemoryEventBus,
)

_AT = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
_PINGED = "Pinged"


@pytest.fixture
def recorder():
    recorder = BusEventRecorder(capacity=3, clock=lambda: _AT)
    recorder.start()
    yield recorder
    recorder.stop()


def test_an_emit_is_recorded_with_how_many_handlers_heard_it(recorder) -> None:
    bus = MemoryEventBus()
    bus.on(_PINGED, lambda _event: None)

    bus.emit(_PINGED)

    (record,) = recorder.drain()
    assert record == BusEventRecord(at=_AT, event=_PINGED, handlers=1)
    assert record.outcome == "delivered to 1 handler"


def test_an_emit_nobody_hears_says_so(recorder) -> None:
    MemoryEventBus().emit(_PINGED)

    (record,) = recorder.drain()
    assert record.outcome == "no handler"


def test_a_handler_that_raises_is_its_own_record(recorder) -> None:
    def broken(_event: object) -> None:
        raise RuntimeError("boom")

    bus = MemoryEventBus()
    bus.on(_PINGED, broken)

    bus.emit(_PINGED)

    emitted, failed = recorder.drain()
    assert emitted.handlers == 1
    assert failed.handlers is None
    assert failed.outcome.startswith("failed in ")
    assert "RuntimeError: boom" in failed.outcome


def test_drain_hands_each_record_over_once(recorder) -> None:
    bus = MemoryEventBus()
    bus.emit(_PINGED)

    assert len(recorder.drain()) == 1
    assert recorder.drain() == ()


def test_the_buffer_keeps_the_newest_and_counts_what_it_lost(recorder) -> None:
    """A burst between two drains must not grow without bound (the UI thread
    may be busy): the oldest go, and the loss is counted, never silent."""
    for handler_count in range(5):
        recorder.event_emitted(f"E{handler_count}", handler_count)

    assert [record.event for record in recorder.drain()] == ["E2", "E3", "E4"]
    assert recorder.lost == 2


def test_stop_leaves_the_bus_unobserved() -> None:
    recorder = BusEventRecorder()
    recorder.start()
    assert recorder in bus_observers()

    recorder.stop()

    assert recorder not in bus_observers()
    MemoryEventBus().emit(_PINGED)
    assert recorder.drain() == ()
