from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from Sagittarius_Elite_Warrior.src.domain.events.signal_generated_event import SignalGeneratedEvent
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal import Signal
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import SignalAction


def test_signal_generated_event_initialization():
    """Test successful initialization of SignalGeneratedEvent."""
    signal = Signal(
        symbol="BTC/USD",
        action=SignalAction.BUY,
        reason="RSI Oversold",
        price=50000.0,
        time=datetime(2023, 1, 1, 12, 0, 0)
    )
    event = SignalGeneratedEvent(signal=signal)

    assert event.signal == signal
    assert event.signal.symbol == "BTC/USD"
    assert event.signal.action == SignalAction.BUY
    assert event.signal.reason == "RSI Oversold"
    assert event.signal.price == 50000.0
    assert event.signal.time == datetime(2023, 1, 1, 12, 0, 0)


def test_signal_generated_event_immutability():
    """Test that SignalGeneratedEvent is immutable (frozen)."""
    signal1 = Signal(
        symbol="BTC/USD",
        action=SignalAction.BUY,
        reason="RSI Oversold",
        price=50000.0,
        time=datetime(2023, 1, 1, 12, 0, 0)
    )
    event = SignalGeneratedEvent(signal=signal1)

    signal2 = Signal(
        symbol="ETH/USD",
        action=SignalAction.SELL,
        reason="MACD Cross",
        price=3000.0,
        time=datetime(2023, 1, 2, 12, 0, 0)
    )

    with pytest.raises(FrozenInstanceError):
        event.signal = signal2
