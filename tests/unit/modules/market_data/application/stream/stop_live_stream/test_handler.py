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


def test_an_owner_holding_nothing_is_not_a_warning(caplog):
    """`BUG-160`: a chart's unconditional stop of a stream that never opened
    (its 1s sync had failed) logged `WARNING`, which the run-log scan fails on."""
    stream_service = Mock()
    stream_service.release_owner.return_value = False
    handler = StopLiveStreamCommandHandler(stream_service)

    with caplog.at_level("DEBUG"):
        handler.execute(StopLiveStreamCommand(owner="market.BTCUSDT"))

    assert [r for r in caplog.records if r.levelname in ("WARNING", "ERROR")] == []
