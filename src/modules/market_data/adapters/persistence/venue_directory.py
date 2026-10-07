"""Where each market-data venue keeps its candles (`BUG-172`).

The candle store is keyed by the venue it was fetched from as well as by market,
symbol and interval, so a testnet candle is never served as a mainnet one. The
key is a directory: `MAINNET_PUBLIC` keeps the configured directory itself, as
every install did before the key existed (every shard already there was
downloaded from the mainnet, ADR O3), and each testnet gets a subdirectory named
by its value. `SqliteShardManager` lists `*.db` files of one directory only, so
a venue's gap scan, export, purge and vacuum never reach another venue's shards.
"""

from __future__ import annotations

import os

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from sagittarius_engine.extensions.persistence.sqlite_shard_manager import IN_MEMORY


def venue_directory(base: str, venue: MarketDataVenue) -> str:
    """@brief The directory of `venue`'s shards under the configured `base`.

    @details `IN_MEMORY` is returned as it is: a `DatabaseManager` of its own is
    already a store of its own in memory, and joining a path onto the sentinel
    would turn it into a real filesystem path (`shard_name()`).
    """
    if venue is MarketDataVenue.MAINNET_PUBLIC or base == IN_MEMORY:
        return base
    return os.path.join(base, venue.value)
