"""Fixtures shared by the Backtest UI tests."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)


@pytest.fixture
def notifier() -> RecordingNotifier:
    """What the Backtest screen told the user (`BOT-169`); the composition
    root binds the real one, and a presenter test asserts on this."""
    return RecordingNotifier()
