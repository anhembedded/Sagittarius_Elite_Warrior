"""`BUG-172` — each market-data venue keeps its candles in a store of its own."""

from __future__ import annotations

import os

import pytest
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.venue_directory import (
    venue_directory,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from sagittarius_engine.extensions.persistence.sqlite_shard_manager import IN_MEMORY


def test_the_mainnet_keeps_the_configured_directory_as_every_install_had_it() -> None:
    """Every shard already on disk was downloaded from the mainnet (ADR O3), so
    it stays where it is and stays the mainnet's."""
    assert venue_directory("data/db", MarketDataVenue.MAINNET_PUBLIC) == "data/db"


@pytest.mark.parametrize(
    "venue", [MarketDataVenue.FUTURES_TESTNET, MarketDataVenue.SPOT_TESTNET]
)
def test_a_testnet_gets_a_subdirectory_named_by_its_value(
    venue: MarketDataVenue,
) -> None:
    assert venue_directory("data/db", venue) == os.path.join("data/db", venue.value)


def test_no_two_venues_share_a_directory() -> None:
    directories = {venue_directory("data/db", venue) for venue in MarketDataVenue}

    assert len(directories) == len(MarketDataVenue)


def test_the_in_memory_sentinel_is_never_turned_into_a_path() -> None:
    """Joined onto, `":memory:"` would stop matching the sentinel and become a real
    filesystem path; a manager of its own is already a store of its own in memory."""
    assert {venue_directory(IN_MEMORY, venue) for venue in MarketDataVenue} == {
        IN_MEMORY
    }
