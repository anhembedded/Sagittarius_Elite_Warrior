from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.start_live_stream.command import (
    StartLiveStreamCommand,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.start_live_stream.handler import (
    StartLiveStreamCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_venues import (
    FakeMarketDataVenues,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)


def test_execute_forwards_owner_market_symbols_and_interval_to_subscribe():
    """`BOT-126` — the handler is the only place translating the command's
    `owner` into the port's `subscribe()` call; a typo/param-order slip here
    would silently scope every subscription wrong."""
    stream_service = Mock()
    stream_service.subscribe.return_value = True
    handler = StartLiveStreamCommandHandler(
        FakeMarketDataVenues(Mock(), Mock(), stream_service)
    )

    response = handler.execute(
        StartLiveStreamCommand(
            owner="trading",
            market_type=MarketType.SPOT,
            symbols=["BTCUSDT"],
            interval=TimeFrame.ONE_MINUTE,
        )
    )

    stream_service.subscribe.assert_called_once_with(
        "trading", MarketType.SPOT, ["BTCUSDT"], TimeFrame.ONE_MINUTE
    )
    assert response.success is True


def test_execute_reports_failure_when_subscribe_returns_false():
    stream_service = Mock()
    stream_service.subscribe.return_value = False
    handler = StartLiveStreamCommandHandler(
        FakeMarketDataVenues(Mock(), Mock(), stream_service)
    )

    response = handler.execute(
        StartLiveStreamCommand(
            owner="dashboard",
            market_type=MarketType.SPOT,
            symbols=["ETHUSDT"],
            interval=TimeFrame.FIVE_MINUTES,
        )
    )

    assert response.success is False


def test_a_start_subscribes_on_the_stream_of_the_venue_it_names():
    """`BUG-172` — the owner's subscription is held by that venue's connection and
    no other's: the testnet's candles must not flow through the mainnet stream."""
    default_stream, testnet_stream = Mock(), Mock()
    testnet_stream.subscribe.return_value = True
    venues = FakeMarketDataVenues(Mock(), Mock(), default_stream).for_venue(
        MarketDataVenue.SPOT_TESTNET, Mock(), Mock(), testnet_stream
    )

    StartLiveStreamCommandHandler(venues).execute(
        StartLiveStreamCommand(
            owner="desk.spot_testnet",
            market_type=MarketType.SPOT,
            symbols=["BTCUSDT"],
            interval=TimeFrame.ONE_MINUTE,
            venue=MarketDataVenue.SPOT_TESTNET,
        )
    )

    testnet_stream.subscribe.assert_called_once()
    default_stream.subscribe.assert_not_called()
