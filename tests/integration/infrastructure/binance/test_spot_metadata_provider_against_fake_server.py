"""`EPIC-027I` — `SpotMetadataProvider` against a real HTTP round trip.

@details Same reasoning as `test_futures_metadata_provider_against_fake_
server.py`: `create_metadata_client()` constructs a real
`binance.client.Client`, so this needs either a real network (blocked in
this sandbox by design) or a local substitute — reuses
`tests/sanity/binance_fake_server.py` and its existing
`fake_exchange/spot_routes.py::_SPOT_EXCHANGE_INFO` fixture (`EPIC-027J`)
rather than inventing a second one.

Not the sanity `booted_app` fixture: this doesn't need a full app boot,
only `SpotSessionFactory` + the real cache, so going through a second boot
would repeat the exact mistake `EPIC-009` already paid to fix.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from binance.client import Client
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.symbol_order_metadata_cache import (
    InMemorySymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_metadata_provider import (
    SpotMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_session_factory import (
    SpotSessionFactory,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tests" / "sanity"))
from binance_fake_server import run_binance_fake_server


def test_refresh_round_trips_real_filter_values_from_the_fake_server():
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        session_factory = SpotSessionFactory()
        cache = InMemorySymbolOrderMetadataCache()
        provider = SpotMetadataProvider(session_factory, cache)

        metadata = provider.get_or_fetch("BTCUSDT")

        assert metadata is not None
        assert metadata.step_size == Decimal("0.00001")
        assert metadata.tick_size == Decimal("0.01")
        assert metadata.min_notional == Decimal(5)
        assert metadata.quantity_precision is None
        assert metadata.price_precision is None
        assert cache.has("ETHUSDT"), "the whole catalog is cached, not just BTCUSDT"


def test_a_cache_hit_issues_no_second_request():
    """Proves the cache-first contract end to end: stop the fake server
    after the first fetch, and a second `get_or_fetch()` for an
    already-cached symbol must still succeed."""
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        session_factory = SpotSessionFactory()
        cache = InMemorySymbolOrderMetadataCache()
        provider = SpotMetadataProvider(session_factory, cache)
        provider.get_or_fetch("BTCUSDT")

    # The fake server is now stopped (context manager exited) — a second
    # `create_metadata_client()` call would fail to connect.
    assert provider.get_or_fetch("BTCUSDT") is not None
