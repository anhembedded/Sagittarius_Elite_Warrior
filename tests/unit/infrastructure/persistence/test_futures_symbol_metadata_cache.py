from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.domain.entities.futures_symbol_metadata import (
    FuturesSymbolMetadata,
)
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.futures_symbol_metadata_cache import (
    InMemoryFuturesSymbolMetadataCache,
)


def _metadata(symbol: str = "BTCUSDT") -> FuturesSymbolMetadata:
    return FuturesSymbolMetadata(
        symbol=symbol,
        status="TRADING",
        step_size=Decimal("0.001"),
        tick_size=Decimal("0.10"),
        min_notional=Decimal(100),
        quantity_precision=3,
        price_precision=2,
        fetched_at=datetime(2026, 9, 1, tzinfo=UTC),
    )


def test_a_symbol_not_yet_stored_is_absent():
    cache = InMemoryFuturesSymbolMetadataCache()
    assert cache.get("BTCUSDT") is None
    assert cache.has("BTCUSDT") is False


def test_put_then_get_round_trips():
    cache = InMemoryFuturesSymbolMetadataCache()
    metadata = _metadata()

    cache.put(metadata)

    assert cache.get("BTCUSDT") == metadata
    assert cache.has("BTCUSDT") is True


def test_lookup_is_case_insensitive():
    cache = InMemoryFuturesSymbolMetadataCache()
    cache.put(_metadata("BTCUSDT"))

    assert cache.get("btcusdt") is not None
    assert cache.has("btcusdt") is True


def test_a_second_put_for_the_same_symbol_overwrites_the_first():
    cache = InMemoryFuturesSymbolMetadataCache()
    cache.put(_metadata("BTCUSDT"))
    updated = FuturesSymbolMetadata(
        symbol="BTCUSDT",
        status="TRADING",
        step_size=Decimal("0.01"),
        tick_size=Decimal("0.10"),
        min_notional=Decimal(100),
        quantity_precision=2,
        price_precision=2,
        fetched_at=datetime(2026, 9, 2, tzinfo=UTC),
    )

    cache.put(updated)

    assert cache.get("BTCUSDT") == updated


def test_clear_empties_the_cache():
    cache = InMemoryFuturesSymbolMetadataCache()
    cache.put(_metadata("BTCUSDT"))
    cache.put(_metadata("ETHUSDT"))

    cache.clear()

    assert cache.get("BTCUSDT") is None
    assert cache.get("ETHUSDT") is None
