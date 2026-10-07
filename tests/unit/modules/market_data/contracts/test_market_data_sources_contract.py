"""`IMarketDataSources` (`BUG-172`): each venue's ports are its own, and the same
every time they are asked for.

@details Both implementations are unit tests, for the reason
`test_market_data_sync_contract.py` gives: the real one only assembles the
module's own services over a venue's store, and the fake is what every
consumer's test drives.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.application.market_data_sources import (
    MarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sources import (
    IMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    candle,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_repository import (
    FakeMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sources import (
    FakeMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_venues import (
    FakeMarketDataVenues,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)

_MAINNET = MarketDataVenue.MAINNET_PUBLIC
_TESTNET = MarketDataVenue.SPOT_TESTNET
_MINUTE = TimeFrame.ONE_MINUTE


def _real() -> tuple[
    IMarketDataSources, dict[MarketDataVenue, FakeMarketDataRepository]
]:
    stores = {venue: FakeMarketDataRepository() for venue in MarketDataVenue}
    venues = FakeMarketDataVenues(Mock(), stores[_MAINNET], Mock(), default=_MAINNET)
    for venue in (MarketDataVenue.FUTURES_TESTNET, _TESTNET):
        venues.for_venue(venue, Mock(), stores[venue], Mock())
    return MarketDataSources(Mock(), venues), stores


@pytest.mark.parametrize("venue", list(MarketDataVenue))
def test_the_ports_are_bound_to_the_venue_asked_for(venue: MarketDataVenue) -> None:
    sources, _ = _real()

    assert sources.ports_for(venue).venue is venue


def test_the_same_venue_answers_with_the_same_ports_every_time() -> None:
    """A stream owner and its sync agree only if they come from one object."""
    sources, _ = _real()

    assert sources.ports_for(_TESTNET) is sources.ports_for(_TESTNET)
    assert sources.ports_for(_TESTNET) is not sources.ports_for(_MAINNET)


def test_the_default_venue_is_the_venues_default() -> None:
    sources, _ = _real()

    assert sources.default_venue is _MAINNET


def test_a_venues_history_reads_that_venues_store_only() -> None:
    sources, stores = _real()
    stores[_TESTNET].save_klines(MarketType.SPOT, [candle("BTCUSDT", 0)])

    on_testnet = sources.ports_for(_TESTNET).history.load(
        MarketType.SPOT, "BTCUSDT", _MINUTE
    )
    on_mainnet = sources.ports_for(_MAINNET).history.load(
        MarketType.SPOT, "BTCUSDT", _MINUTE
    )

    assert len(on_testnet) == 1
    assert on_mainnet == ()


def test_the_exposed_repository_is_the_store_history_and_coverage_read() -> None:
    sources, stores = _real()

    assert sources.ports_for(_TESTNET).repository is stores[_TESTNET]


class TestTheFake:
    def test_an_unregistered_venue_is_an_error_not_a_stand_in(self) -> None:
        sources = FakeMarketDataSources()

        with pytest.raises(AssertionError, match="spot_testnet"):
            sources.ports_for(_TESTNET)

    def test_a_registered_venue_answers_with_its_ports_and_the_ask_is_recorded(
        self,
    ) -> None:
        ports = FakeMarketDataSources.ports(_TESTNET)
        sources = FakeMarketDataSources().serving(ports)

        assert sources.ports_for(_TESTNET) is ports
        assert sources.asked == [_TESTNET]

    def test_the_ports_it_builds_are_its_own_per_venue(self) -> None:
        mainnet = FakeMarketDataSources.ports(_MAINNET)
        testnet = FakeMarketDataSources.ports(_TESTNET)

        assert mainnet.venue is _MAINNET and testnet.venue is _TESTNET
        assert mainnet.history is not testnet.history
        assert mainnet.repository is not testnet.repository

    def test_a_port_given_to_it_is_the_one_it_hands_back(self) -> None:
        repository = FakeMarketDataRepository()

        ports = FakeMarketDataSources.ports(_TESTNET, repository=repository)

        assert ports.repository is repository

    def test_its_default_venue_is_the_one_it_was_built_with(self) -> None:
        assert FakeMarketDataSources(default=_TESTNET).default_venue is _TESTNET
