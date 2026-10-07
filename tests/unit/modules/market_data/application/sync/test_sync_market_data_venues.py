"""`BUG-172` — a sync fetches from, and stores into, the venue its command names.

@details One handler serves every venue: the exchange client and the candle store
it uses are the ones `IMarketDataVenues` hands out for `command.venue`, and a
command naming none means the default venue (`exchange.market_data_venue`).
"""

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.application.sync.in_flight_sync_guard import (
    InFlightSyncGuard,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.sync.sync_market_data import (
    SyncMarketDataCommand,
    SyncMarketDataCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_venues import (
    FakeMarketDataVenues,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)


@pytest.fixture
def mock_event_bus():
    return Mock()


@pytest.fixture
def in_flight_guard():
    return InFlightSyncGuard()


@pytest.fixture
def mock_exchange_client():
    return Mock()


@pytest.fixture
def mock_repo():
    return Mock()


@pytest.fixture
def handler(mock_exchange_client, mock_repo, mock_event_bus, in_flight_guard):
    venues = FakeMarketDataVenues(mock_exchange_client, mock_repo, Mock())
    return SyncMarketDataCommandHandler(venues, mock_event_bus, in_flight_guard)


def test_a_sync_reads_the_exchange_and_writes_the_store_of_the_venue_it_names(
    mock_event_bus, in_flight_guard
):
    """`BUG-172` — the testnet's klines are fetched from the testnet's exchange and
    stored in the testnet's store; the mainnet's client and store are not touched."""
    mainnet_client, mainnet_repo = Mock(), Mock()
    testnet_client, testnet_repo = Mock(), Mock()
    testnet_repo.get_latest_kline_time.return_value = None
    klines = [Mock(spec=MarketData)]
    testnet_client.stream_historical_klines.return_value = iter([klines])
    venues = FakeMarketDataVenues(mainnet_client, mainnet_repo, Mock()).for_venue(
        MarketDataVenue.SPOT_TESTNET, testnet_client, testnet_repo, Mock()
    )

    SyncMarketDataCommandHandler(venues, mock_event_bus, in_flight_guard).execute(
        SyncMarketDataCommand(
            market=MarketType.SPOT,
            symbols=["BTCUSDT"],
            interval=TimeFrame.ONE_MINUTE,
            venue=MarketDataVenue.SPOT_TESTNET,
        )
    )

    testnet_repo.save_klines.assert_called_once_with(MarketType.SPOT, klines)
    mainnet_client.stream_historical_klines.assert_not_called()
    mainnet_repo.save_klines.assert_not_called()


def test_a_sync_naming_no_venue_uses_the_default_one(
    mock_event_bus, in_flight_guard, mock_exchange_client, mock_repo
):
    """The CLI, the bulk sync and Data mode act on no venue."""
    mock_repo.get_latest_kline_time.return_value = None
    klines = [Mock(spec=MarketData)]
    mock_exchange_client.stream_historical_klines.return_value = iter([klines])
    venues = FakeMarketDataVenues(
        mock_exchange_client,
        mock_repo,
        Mock(),
        default=MarketDataVenue.FUTURES_TESTNET,
    )

    SyncMarketDataCommandHandler(venues, mock_event_bus, in_flight_guard).execute(
        SyncMarketDataCommand(
            market=MarketType.SPOT, symbols=["BTCUSDT"], interval=TimeFrame.ONE_MINUTE
        )
    )

    mock_repo.save_klines.assert_called_once_with(MarketType.SPOT, klines)


def test_two_venues_syncing_the_same_symbol_do_not_exclude_each_other(
    handler, in_flight_guard, mock_repo, mock_exchange_client
):
    """`BUG-172` — a Spot Testnet desk and a Spot Mainnet desk open on the same
    `BTCUSDT 1m` together; a sync skipped as "in flight elsewhere" would leave
    one chart empty."""
    assert in_flight_guard.try_acquire(
        "spot_testnet/spot", "BTCUSDT", TimeFrame.ONE_MINUTE.value
    )
    mock_repo.get_latest_kline_time.return_value = None
    mock_exchange_client.stream_historical_klines.return_value = iter([[]])

    handler.execute(
        SyncMarketDataCommand(
            market=MarketType.SPOT, symbols=["BTCUSDT"], interval=TimeFrame.ONE_MINUTE
        )
    )

    mock_exchange_client.stream_historical_klines.assert_called_once()
