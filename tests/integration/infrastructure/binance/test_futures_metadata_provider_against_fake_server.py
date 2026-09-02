"""`EPIC-021C` — `FuturesMetadataProvider` against a real HTTP round trip.

@details Same reasoning as `test_exchange_session_factory_against_fake_
server.py` (`EPIC-021A`): `create_futures_metadata_client()` constructs a
real `binance.client.Client`, so this needs either a real network (blocked
in this sandbox by design) or a local substitute — reuses
`tests/sanity/binance_fake_server.py` rather than inventing a second fake.

Not the sanity `booted_app` fixture: this doesn't need a full app boot,
only `ExchangeSessionFactory` + the real cache, so going through a second
boot would repeat the exact mistake `EPIC-009` already paid to fix.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from binance.client import Client
from Sagittarius_Elite_Warrior.src.domain.value_objects.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.exchange_session_factory import (
    ExchangeSessionFactory,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.futures_metadata_provider import (
    FuturesMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.futures_symbol_metadata_cache import (
    InMemoryFuturesSymbolMetadataCache,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tests" / "sanity"))
from binance_fake_server import run_binance_fake_server


def test_refresh_round_trips_real_filter_values_from_the_fake_server():
    with (
        run_binance_fake_server() as urls,
        # `Client(testnet=True)`'s constructor pings on construction by
        # default (`ping=True`) — always the SPOT path (`API_TESTNET_URL`),
        # regardless of what the client is actually going to be used for.
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        # The factory's own `market_data_venue` doesn't matter here — see
        # `create_futures_metadata_client()`'s docstring for why it always
        # targets Futures Testnet regardless.
        session_factory = ExchangeSessionFactory(MarketDataVenue.MAINNET_PUBLIC)
        cache = InMemoryFuturesSymbolMetadataCache()
        provider = FuturesMetadataProvider(session_factory, cache)

        metadata = provider.get_or_fetch("BTCUSDT")

        assert metadata is not None
        assert metadata.step_size == Decimal("0.001")
        assert metadata.tick_size == Decimal("0.10")
        assert metadata.min_notional == Decimal(100)
        assert metadata.quantity_precision == 3
        assert cache.has("ETHUSDT"), "the whole catalog is cached, not just BTCUSDT"


def test_a_cache_hit_issues_no_second_request():
    """Proves the cache-first contract end to end: stop the fake server
    after the first fetch, and a second `get_or_fetch()` for an
    already-cached symbol must still succeed."""
    with (
        run_binance_fake_server() as urls,
        # `Client(testnet=True)`'s constructor pings on construction by
        # default (`ping=True`) — always the SPOT path (`API_TESTNET_URL`),
        # regardless of what the client is actually going to be used for.
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        session_factory = ExchangeSessionFactory(MarketDataVenue.MAINNET_PUBLIC)
        cache = InMemoryFuturesSymbolMetadataCache()
        provider = FuturesMetadataProvider(session_factory, cache)
        provider.get_or_fetch("BTCUSDT")

    # The fake server is now stopped (context manager exited) — a second
    # `create_futures_metadata_client()` call would fail to connect.
    assert provider.get_or_fetch("BTCUSDT") is not None
