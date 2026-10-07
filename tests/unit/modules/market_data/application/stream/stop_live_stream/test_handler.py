from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.stop_live_stream.command import (
    StopLiveStreamCommand,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.stop_live_stream.handler import (
    StopLiveStreamCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_venues import (
    FakeMarketDataVenues,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)


def test_execute_forwards_owner_to_release_owner():
    """`BOT-126` — the handler is the only place translating the command's
    `owner` into the port's `release_owner()` call; forgetting to forward it
    (or forwarding the wrong owner) would resurrect the old "stop
    everything" behaviour or release the wrong screen's stream."""
    stream_service = Mock()
    stream_service.release_owner.return_value = True
    handler = StopLiveStreamCommandHandler(
        FakeMarketDataVenues(Mock(), Mock(), stream_service)
    )

    response = handler.execute(StopLiveStreamCommand(owner="trading"))

    stream_service.release_owner.assert_called_once_with("trading")
    assert response.success is True


def test_execute_reports_failure_when_owner_had_nothing_running():
    stream_service = Mock()
    stream_service.release_owner.return_value = False
    handler = StopLiveStreamCommandHandler(
        FakeMarketDataVenues(Mock(), Mock(), stream_service)
    )

    response = handler.execute(StopLiveStreamCommand(owner="dashboard"))

    assert response.success is False


def test_an_owner_holding_nothing_is_not_a_warning(caplog):
    """`BUG-160`: a chart's unconditional stop of a stream that never opened
    (its 1s sync had failed) logged `WARNING`, which the run-log scan fails on."""
    stream_service = Mock()
    stream_service.release_owner.return_value = False
    handler = StopLiveStreamCommandHandler(
        FakeMarketDataVenues(Mock(), Mock(), stream_service)
    )

    with caplog.at_level("DEBUG"):
        handler.execute(StopLiveStreamCommand(owner="market.BTCUSDT"))

    assert [r for r in caplog.records if r.levelname in ("WARNING", "ERROR")] == []


def test_a_stop_releases_the_owner_on_the_stream_of_the_venue_it_names():
    default_stream, testnet_stream = Mock(), Mock()
    testnet_stream.release_owner.return_value = True
    venues = FakeMarketDataVenues(Mock(), Mock(), default_stream).for_venue(
        MarketDataVenue.SPOT_TESTNET, Mock(), Mock(), testnet_stream
    )

    StopLiveStreamCommandHandler(venues).execute(
        StopLiveStreamCommand(
            owner="desk.spot_testnet", venue=MarketDataVenue.SPOT_TESTNET
        )
    )

    testnet_stream.release_owner.assert_called_once_with("desk.spot_testnet")
    default_stream.release_owner.assert_not_called()
