from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal import Signal
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)


def test_signal_initialization():
    """Test successful initialization of Signal."""
    signal_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
    signal = Signal(
        symbol="BTCUSDT",
        action=SignalAction.BUY,
        reason="MACD crossover",
        price=30000.0,
        time=signal_time,
    )

    assert signal.symbol == "BTCUSDT"
    assert signal.action == SignalAction.BUY
    assert signal.reason == "MACD crossover"
    assert signal.price == 30000.0
    assert signal.time == signal_time


def test_signal_immutability():
    """Test that Signal instances are frozen (immutable)."""
    signal_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
    signal = Signal(
        symbol="BTCUSDT",
        action=SignalAction.BUY,
        reason="MACD crossover",
        price=30000.0,
        time=signal_time,
    )

    with pytest.raises(FrozenInstanceError):
        signal.price = 31000.0

    with pytest.raises(FrozenInstanceError):
        signal.action = SignalAction.SELL
