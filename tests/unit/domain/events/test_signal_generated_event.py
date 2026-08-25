from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.domain.events.signal_generated_event import (
    SignalGeneratedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal import Signal
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)


def test_signal_generated_event_initialization():
    """Test successful initialization of SignalGeneratedEvent."""
    signal = Signal(
        symbol="BTC/USD",
        action=SignalAction.BUY,
        reason="RSI Oversold",
        price=50000.0,
        time=datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC),
    )
    event = SignalGeneratedEvent(signal=signal)

    assert event.signal == signal
    assert event.signal.symbol == "BTC/USD"
    assert event.signal.action == SignalAction.BUY
    assert event.signal.reason == "RSI Oversold"
    assert event.signal.price == 50000.0
    assert event.signal.time == datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)


def test_signal_generated_event_is_no_longer_frozen():
    """`EPIC-008F` traded `frozen=True` away, deliberately — user's call.

    This test asserted `FrozenInstanceError` before. Domain events now inherit
    the engine's `BaseEvent` so `EventRegistry` can catalog them (`EPIC-008B`),
    and Python forbids a frozen dataclass from inheriting a non-frozen one.
    `BaseEvent` cannot become frozen either: it supports subclasses with a
    hand-written `__init__` that assign attributes — the engine's own
    `HealthUpdatedEvent` is one — which freezing would break.

    Kept rather than deleted, and asserting the *new* behaviour rather than
    silently dropping the old one, so the loss stays visible: mutability here
    is now a convention, not a guarantee. A handler that mutates an event
    mutates it for every later subscriber in the same fan-out. If a future
    change makes freezing possible again, this test failing is the reminder to
    restore it.
    """
    event = SignalGeneratedEvent(
        signal=Signal(
            symbol="BTC/USD",
            action=SignalAction.BUY,
            reason="RSI Oversold",
            price=50000.0,
            time=datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC),
        )
    )

    replacement = Signal(
        symbol="ETH/USD",
        action=SignalAction.SELL,
        reason="MACD Cross",
        price=3000.0,
        time=datetime(2023, 1, 2, 12, 0, 0, tzinfo=UTC),
    )

    event.signal = replacement  # no FrozenInstanceError any more
    assert event.signal is replacement


def test_events_with_the_same_payload_compare_equal():
    """Guards the other half of the `BaseEvent` move: `_event_id` is unique per
    instance and must not reach `__eq__`, or two identical events would never
    compare equal. Fixed engine-side with `compare=False`; asserted here
    because this repo is where the breakage showed up."""
    signal = Signal(
        symbol="BTC/USD",
        action=SignalAction.BUY,
        reason="RSI Oversold",
        price=50000.0,
        time=datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC),
    )

    assert SignalGeneratedEvent(signal=signal) == SignalGeneratedEvent(signal=signal)
