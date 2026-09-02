"""`EPIC-021C` — `futures_metadata_parser`, against a static fixture payload
(no network call — see the parser's own module docstring for why the shape
below isn't live-verified)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.infrastructure.binance.futures_metadata_parser import (
    DEFAULT_MIN_NOTIONAL,
    DEFAULT_PRICE_PRECISION,
    DEFAULT_QUANTITY_PRECISION,
    DEFAULT_STATUS,
    DEFAULT_STEP_SIZE,
    DEFAULT_TICK_SIZE,
    parse_futures_exchange_info,
    parse_futures_symbol_metadata,
)

_FIXED_TIME = datetime(2026, 9, 1, tzinfo=UTC)

_BTCUSDT_ENTRY = {
    "symbol": "BTCUSDT",
    "status": "TRADING",
    "pricePrecision": 2,
    "quantityPrecision": 3,
    "filters": [
        {
            "filterType": "PRICE_FILTER",
            "minPrice": "556.80",
            "maxPrice": "4529764",
            "tickSize": "0.10",
        },
        {
            "filterType": "LOT_SIZE",
            "minQty": "0.001",
            "maxQty": "1000",
            "stepSize": "0.001",
        },
        {
            "filterType": "MARKET_LOT_SIZE",
            "minQty": "0.001",
            "maxQty": "120",
            "stepSize": "0.001",
        },
        {"filterType": "MIN_NOTIONAL", "notional": "100"},
    ],
}

_EXCHANGE_INFO_PAYLOAD = {
    "timezone": "UTC",
    "serverTime": 0,
    "symbols": [_BTCUSDT_ENTRY],
}


def test_parses_every_field_from_a_complete_entry():
    metadata = parse_futures_symbol_metadata(_BTCUSDT_ENTRY, fetched_at=_FIXED_TIME)

    assert metadata.symbol == "BTCUSDT"
    assert metadata.status == "TRADING"
    assert metadata.tick_size == Decimal("0.10")
    assert metadata.step_size == Decimal("0.001")
    assert metadata.min_notional == Decimal(100)
    assert metadata.quantity_precision == 3
    assert metadata.price_precision == 2
    assert metadata.fetched_at == _FIXED_TIME


def test_decimal_fields_are_exact_not_a_float_approximation():
    """The whole reason this parser exists separately from spot's `float`
    one — `Decimal("0.10")` must be exactly `0.1`, not a binary-fraction
    neighbor of it."""
    metadata = parse_futures_symbol_metadata(_BTCUSDT_ENTRY, fetched_at=_FIXED_TIME)

    assert metadata.tick_size == Decimal("0.10")
    assert str(metadata.tick_size) in ("0.10", "0.1")


def test_a_symbol_missing_every_filter_gets_named_defaults_not_a_crash():
    bare_entry = {"symbol": "NEWUSDT", "status": "TRADING"}

    metadata = parse_futures_symbol_metadata(bare_entry, fetched_at=_FIXED_TIME)

    assert metadata.tick_size == DEFAULT_TICK_SIZE
    assert metadata.step_size == DEFAULT_STEP_SIZE
    assert metadata.min_notional == DEFAULT_MIN_NOTIONAL
    assert metadata.quantity_precision == DEFAULT_QUANTITY_PRECISION
    assert metadata.price_precision == DEFAULT_PRICE_PRECISION


def test_a_missing_status_defaults_to_trading():
    metadata = parse_futures_symbol_metadata({"symbol": "X"}, fetched_at=_FIXED_TIME)
    assert metadata.status == DEFAULT_STATUS


def test_min_notional_accepts_the_spot_shaped_key_too_defensively():
    """Futures uses `"notional"`; this accepts spot's `"minNotional"` key
    too, defensively, in case a future API revision changes the shape —
    documented explicitly in the parser, not an accident."""
    entry = {
        "symbol": "X",
        "filters": [{"filterType": "MIN_NOTIONAL", "minNotional": "20"}],
    }
    metadata = parse_futures_symbol_metadata(entry, fetched_at=_FIXED_TIME)
    assert metadata.min_notional == Decimal(20)


def test_a_non_dict_filter_entry_is_skipped_not_fatal():
    entry = {"symbol": "X", "filters": ["not-a-dict", {"filterType": "unknown"}]}
    metadata = parse_futures_symbol_metadata(entry, fetched_at=_FIXED_TIME)
    assert metadata.step_size == DEFAULT_STEP_SIZE


def test_parse_futures_exchange_info_returns_one_entry_per_symbol():
    results = parse_futures_exchange_info(
        _EXCHANGE_INFO_PAYLOAD, fetched_at=_FIXED_TIME
    )

    assert len(results) == 1
    assert results[0].symbol == "BTCUSDT"


def test_parse_futures_exchange_info_skips_a_non_dict_symbol_entry():
    payload = {"symbols": [_BTCUSDT_ENTRY, "not-a-dict", 42]}

    results = parse_futures_exchange_info(payload, fetched_at=_FIXED_TIME)

    assert len(results) == 1


def test_parse_futures_exchange_info_on_an_empty_catalog_returns_an_empty_list():
    assert parse_futures_exchange_info({"symbols": []}) == []
