"""Which subdirectory of the candle store a market-data venue's shards live in (`BUG-172`).

@details Split from `venue_directory.py` by `EPIC-047H`: the bridge, a second process that starts fast on the VPS
and must import no network library, opens the host's shards read-only and must look in the directory the host
wrote them to. `venue_directory` imports the Engine for its in-memory sentinel, which brings a socket with it;
this does not. One definition, two readers (P3).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)


def venue_subdirectory(venue: MarketDataVenue) -> str:
    """`""` for `MAINNET_PUBLIC`, which keeps the configured directory itself (every install did before the key existed,
    ADR O3); each testnet gets a subdirectory named by its value."""
    return "" if venue is MarketDataVenue.MAINNET_PUBLIC else venue.value
