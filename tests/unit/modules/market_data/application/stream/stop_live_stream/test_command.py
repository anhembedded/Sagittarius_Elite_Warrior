from dataclasses import FrozenInstanceError

import pytest
from pydantic import ValidationError
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.stop_live_stream.command import (
    StopLiveStreamCommand,
    StopLiveStreamResponse,
)


def test_stop_live_stream_command_success():
    command = StopLiveStreamCommand(owner="trading")
    assert command.owner == "trading"


def test_stop_live_stream_command_empty_owner():
    """`BOT-126` — owner is the scope key `release_owner` releases; an
    empty one would be indistinguishable from "no owner"."""
    with pytest.raises(ValidationError) as excinfo:
        StopLiveStreamCommand(owner="  ")

    assert "owner cannot be empty" in str(excinfo.value)


def test_stop_live_stream_response_initialization():
    response = StopLiveStreamResponse(
        success=True, message="Live stream stopped successfully."
    )
    assert response.success is True
    assert response.message == "Live stream stopped successfully."


def test_stop_live_stream_response_frozen():
    response = StopLiveStreamResponse(success=True, message="Stopped")

    with pytest.raises(FrozenInstanceError):
        response.success = False
