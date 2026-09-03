"""`EPIC-021C` — `FuturesMetadataProvider`: cache-first, `refresh()` always
hits the network. Uses a `Mock` only for the SDK-facing boundary
(`ExchangeSessionFactory`/its `Client`) — the cache is the real
`InMemoryFuturesSymbolMetadataCache`, so these tests exercise the actual
cache-hit/miss logic, not a re-implementation of it."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.domain.entities.futures_symbol_metadata import (
    FuturesSymbolMetadata,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.futures_metadata_provider import (
    FuturesMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.futures_symbol_metadata_cache import (
    InMemoryFuturesSymbolMetadataCache,
)

_PAYLOAD = {
    "symbols": [
        {
            "symbol": "BTCUSDT",
            "status": "TRADING",
            "pricePrecision": 2,
            "quantityPrecision": 3,
            "filters": [
                {"filterType": "PRICE_FILTER", "tickSize": "0.10"},
                {"filterType": "LOT_SIZE", "stepSize": "0.001"},
                {"filterType": "MIN_NOTIONAL", "notional": "100"},
            ],
        },
        {
            "symbol": "ETHUSDT",
            "status": "TRADING",
            "pricePrecision": 2,
            "quantityPrecision": 2,
            "filters": [
                {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                {"filterType": "LOT_SIZE", "stepSize": "0.01"},
                {"filterType": "MIN_NOTIONAL", "notional": "20"},
            ],
        },
    ]
}


def _provider():
    raw_client = Mock()
    raw_client.futures_exchange_info.return_value = _PAYLOAD
    session_factory = Mock()
    session_factory.create_futures_metadata_client.return_value = raw_client
    cache = InMemoryFuturesSymbolMetadataCache()
    return FuturesMetadataProvider(session_factory, cache), session_factory, cache


def test_a_cache_miss_fetches_and_caches_the_whole_catalog():
    provider, session_factory, cache = _provider()

    metadata = provider.get_or_fetch("BTCUSDT")

    assert metadata is not None
    assert metadata.symbol == "BTCUSDT"
    assert cache.has("ETHUSDT"), "the whole catalog should be cached, not just BTCUSDT"
    session_factory.create_futures_metadata_client.assert_called_once()


def test_a_cache_hit_does_not_touch_the_network_again():
    provider, session_factory, _cache = _provider()
    provider.get_or_fetch("BTCUSDT")
    session_factory.create_futures_metadata_client.reset_mock()

    provider.get_or_fetch("BTCUSDT")

    session_factory.create_futures_metadata_client.assert_not_called()


def test_a_symbol_absent_from_the_catalog_resolves_to_none_not_a_default():
    provider, _session_factory, _cache = _provider()

    assert provider.get_or_fetch("NOSUCHUSDT") is None


def test_refresh_always_hits_the_network_even_on_a_warm_cache():
    provider, session_factory, _cache = _provider()
    provider.get_or_fetch("BTCUSDT")
    session_factory.create_futures_metadata_client.reset_mock()

    provider.refresh()

    session_factory.create_futures_metadata_client.assert_called_once()


def test_a_stale_cache_hit_forces_a_real_refresh():
    """`BUG-098` — `FuturesSymbolMetadata.is_stale()` existed since
    `BOT-095E1` and was never called in production: once cached, a
    symbol's `stepSize`/`tickSize`/`minNotional` were trusted for the rest
    of the process, even after Binance changes an exchange filter
    server-side."""
    provider, session_factory, cache = _provider()
    stale = FuturesSymbolMetadata(
        symbol="BTCUSDT",
        status="TRADING",
        step_size=Decimal("0.001"),
        tick_size=Decimal("0.10"),
        min_notional=Decimal(100),
        quantity_precision=3,
        price_precision=2,
        fetched_at=datetime.now(UTC) - timedelta(hours=25),
    )
    cache.put(stale)

    metadata = provider.get_or_fetch("BTCUSDT")

    session_factory.create_futures_metadata_client.assert_called_once()
    assert metadata is not None
    assert metadata.fetched_at > stale.fetched_at


def test_refresh_replaces_stale_cached_data():
    provider, session_factory, cache = _provider()
    provider.get_or_fetch("BTCUSDT")
    updated_client = Mock()
    updated_client.futures_exchange_info.return_value = {
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "status": "TRADING",
                "pricePrecision": 2,
                "quantityPrecision": 3,
                "filters": [{"filterType": "MIN_NOTIONAL", "notional": "200"}],
            }
        ]
    }
    session_factory.create_futures_metadata_client.return_value = updated_client

    provider.refresh()

    assert str(cache.get("BTCUSDT").min_notional) == "200"
