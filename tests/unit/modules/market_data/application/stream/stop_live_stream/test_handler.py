from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.stop_live_stream.command import (
    StopLiveStreamCommand,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.stop_live_stream.handler import (
    StopLiveStreamCommandHandler,
)


def test_execute_forwards_owner_to_release_owner():
    """`BOT-126` — the handler is the only place translating the command's
    `owner` into the port's `release_owner()` call; forgetting to forward it
    (or forwarding the wrong owner) would resurrect the old "stop
    everything" behaviour or release the wrong screen's stream."""
    stream_service = Mock()
    stream_service.release_owner.return_value = True
    handler = StopLiveStreamCommandHandler(stream_service)

    response = handler.execute(StopLiveStreamCommand(owner="trading"))

    stream_service.release_owner.assert_called_once_with("trading")
    assert response.success is True


def test_execute_reports_failure_when_owner_had_nothing_running():
    stream_service = Mock()
    stream_service.release_owner.return_value = False
    handler = StopLiveStreamCommandHandler(stream_service)

    response = handler.execute(StopLiveStreamCommand(owner="dashboard"))

    assert response.success is False
