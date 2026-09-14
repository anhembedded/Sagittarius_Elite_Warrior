from dataclasses import FrozenInstanceError

import pytest
from pydantic import ValidationError
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import (
    TimeFrame,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.start_live_stream.command import (
    StartLiveStreamCommand,
    StartLiveStreamResponse,
)


def test_start_live_stream_command_success():
    """Test successful initialization with valid symbols and interval."""
    command = StartLiveStreamCommand(
        owner="trading", symbols=["BTCUSDT", "ETHUSDT"], interval=TimeFrame.ONE_MINUTE
    )
    assert command.owner == "trading"
    assert command.symbols == ["BTCUSDT", "ETHUSDT"]
    assert command.interval == TimeFrame.ONE_MINUTE


def test_start_live_stream_command_empty_symbols():
    """Test that an empty symbols list raises a ValidationError."""
    with pytest.raises(ValidationError) as excinfo:
        StartLiveStreamCommand(
            owner="trading", symbols=[], interval=TimeFrame.ONE_MINUTE
        )

    assert "Symbols list cannot be empty" in str(excinfo.value)


def test_start_live_stream_command_empty_owner():
    """`BOT-126` — owner is the scope key every subscription is released
    by; an empty one would be indistinguishable from "no owner"."""
    with pytest.raises(ValidationError) as excinfo:
        StartLiveStreamCommand(
            owner="  ", symbols=["BTCUSDT"], interval=TimeFrame.ONE_MINUTE
        )

    assert "owner cannot be empty" in str(excinfo.value)


def test_start_live_stream_command_symbols_uppercase():
    """Test that symbol strings are properly uppercased during validation."""
    command = StartLiveStreamCommand(
        owner="trading", symbols=["btcusdt", "ethusdt"], interval=TimeFrame.ONE_MINUTE
    )
    assert command.symbols == ["BTCUSDT", "ETHUSDT"]


def test_start_live_stream_command_invalid_interval():
    """Test that invalid intervals fail validation."""
    with pytest.raises(ValidationError) as excinfo:
        # Pydantic will raise validation error for not being an enum member
        StartLiveStreamCommand(
            owner="trading", symbols=["BTCUSDT"], interval="invalid_interval"
        )

    assert "Input should be" in str(excinfo.value)


def test_start_live_stream_response_initialization():
    """Test successful init of StartLiveStreamResponse & frozen behavior."""
    response = StartLiveStreamResponse(
        success=True, message="Stream started successfully"
    )
    assert response.success is True
    assert response.message == "Stream started successfully"


def test_start_live_stream_response_frozen():
    """Test that StartLiveStreamResponse behaves as a frozen dataclass."""
    response = StartLiveStreamResponse(success=True, message="Started")

    with pytest.raises(FrozenInstanceError):
        response.success = False
