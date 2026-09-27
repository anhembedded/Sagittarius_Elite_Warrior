"""`EPIC-027I` — `spot_metadata_parser`, against a static fixture payload
(no network call — see the parser's own module docstring for why the shape
below isn't live-verified).

The one behaviour this suite exists to prove that
`test_futures_metadata_parser.py` deliberately does not: a missing required
filter or field **raises**, it is never defaulted — the opposite policy from
Futures' own parser, on purpose (`EPIC-027I`'s own acceptance criterion).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_metadata_parser import (
    DEFAULT_STATUS,
    parse_spot_exchange_info,
    parse_spot_symbol_metadata,
)

_FIXED_TIME = datetime(2026, 9, 1, tzinfo=UTC)

_BTCUSDT_ENTRY = {
    "symbol": "BTCUSDT",
    "status": "TRADING",
    "baseAsset": "BTC",
    "quoteAsset": "USDT",
    "filters": [
        {
            "filterType": "PRICE_FILTER",
            "minPrice": "0.01",
            "maxPrice": "1000000.00",
            "tickSize": "0.01",
        },
        {
            "filterType": "LOT_SIZE",
            "minQty": "0.00001",
            "maxQty": "9000.00000000",
            "stepSize": "0.00001",
        },
        {
            "filterType": "MARKET_LOT_SIZE",
            "minQty": "0.00001",
            "maxQty": "100.00000000",
            "stepSize": "0.0001",
        },
        {
            "filterType": "NOTIONAL",
            "minNotional": "5.00000000",
            "applyToMarket": True,
        },
    ],
}

_EXCHANGE_INFO_PAYLOAD = {
    "timezone": "UTC",
    "serverTime": 0,
    "symbols": [_BTCUSDT_ENTRY],
}


def test_parses_every_field_from_a_complete_entry():
    metadata = parse_spot_symbol_metadata(_BTCUSDT_ENTRY, fetched_at=_FIXED_TIME)

    assert metadata.symbol == "BTCUSDT"
    assert metadata.status == "TRADING"
    assert metadata.tick_size == Decimal("0.01")
    assert metadata.step_size == Decimal("0.00001")
    assert metadata.market_step_size == Decimal("0.0001")
    assert metadata.min_notional == Decimal(5)
    assert metadata.quantity_precision is None
    assert metadata.price_precision is None
    assert metadata.fetched_at == _FIXED_TIME


def test_decimal_fields_are_exact_not_a_float_approximation():
    metadata = parse_spot_symbol_metadata(_BTCUSDT_ENTRY, fetched_at=_FIXED_TIME)

    assert metadata.step_size == Decimal("0.00001")
    assert str(metadata.step_size) == "0.00001"


def test_a_missing_market_lot_size_filter_leaves_market_step_size_none():
    """`MARKET_LOT_SIZE` is the one optional filter — most Spot symbols
    never publish it (`EPIC-027I`'s own acceptance criterion, mirrored in
    `SymbolOrderMetadata.step_size_for()`'s fallback)."""
    entry = {
        "symbol": "ETHUSDT",
        "status": "TRADING",
        "filters": [
            f for f in _BTCUSDT_ENTRY["filters"] if f["filterType"] != "MARKET_LOT_SIZE"
        ],
    }

    metadata = parse_spot_symbol_metadata(entry, fetched_at=_FIXED_TIME)

    assert metadata.market_step_size is None


def test_a_missing_status_defaults_to_trading():
    entry = {
        "symbol": "X",
        "filters": _BTCUSDT_ENTRY["filters"],
    }
    metadata = parse_spot_symbol_metadata(entry, fetched_at=_FIXED_TIME)
    assert metadata.status == DEFAULT_STATUS


@pytest.mark.parametrize(
    "missing_filter_type", ["PRICE_FILTER", "LOT_SIZE", "NOTIONAL"]
)
def test_a_missing_required_filter_raises_instead_of_defaulting(missing_filter_type):
    entry = {
        "symbol": "NEWUSDT",
        "status": "TRADING",
        "filters": [
            f
            for f in _BTCUSDT_ENTRY["filters"]
            if f["filterType"] != missing_filter_type
        ],
    }

    with pytest.raises(KeyError, match=missing_filter_type):
        parse_spot_symbol_metadata(entry, fetched_at=_FIXED_TIME)


def test_a_symbol_with_no_filters_at_all_raises():
    entry = {"symbol": "NEWUSDT", "status": "TRADING"}

    with pytest.raises(KeyError):
        parse_spot_symbol_metadata(entry, fetched_at=_FIXED_TIME)


def test_a_filter_missing_its_required_field_raises():
    entry = {
        "symbol": "BADUSDT",
        "status": "TRADING",
        "filters": [
            {"filterType": "PRICE_FILTER", "minPrice": "0.01"},  # no tickSize
            {"filterType": "LOT_SIZE", "stepSize": "0.001"},
            {"filterType": "NOTIONAL", "minNotional": "5"},
        ],
    }

    with pytest.raises(KeyError, match="tickSize"):
        parse_spot_symbol_metadata(entry, fetched_at=_FIXED_TIME)


def test_a_non_dict_filter_entry_is_skipped_not_fatal_on_its_own():
    """Skipping a malformed filter *entry* is still defensive — the
    strictness this parser adds is about a *required filter type or field
    being absent*, not about tolerating garbage list items."""
    entry = {
        "symbol": "BTCUSDT",
        "status": "TRADING",
        "filters": ["not-a-dict", *_BTCUSDT_ENTRY["filters"]],
    }

    metadata = parse_spot_symbol_metadata(entry, fetched_at=_FIXED_TIME)

    assert metadata.step_size == Decimal("0.00001")


def test_parse_spot_exchange_info_returns_one_entry_per_symbol():
    results = parse_spot_exchange_info(_EXCHANGE_INFO_PAYLOAD, fetched_at=_FIXED_TIME)

    assert len(results) == 1
    assert results[0].symbol == "BTCUSDT"


def test_parse_spot_exchange_info_skips_a_non_dict_symbol_entry():
    payload = {"symbols": [_BTCUSDT_ENTRY, "not-a-dict", 42]}

    results = parse_spot_exchange_info(payload, fetched_at=_FIXED_TIME)

    assert len(results) == 1


def test_parse_spot_exchange_info_on_an_empty_catalog_returns_an_empty_list():
    assert parse_spot_exchange_info({"symbols": []}) == []


def test_parse_spot_exchange_info_propagates_a_malformed_symbols_own_error():
    """A defensive per-entry `isinstance` guard skips a garbage list item,
    but a genuinely malformed *dict* entry (missing a required filter) must
    still fail loudly — the whole point of this parser's strict policy."""
    bad_entry = {"symbol": "BADUSDT", "status": "TRADING"}
    payload = {"symbols": [bad_entry]}

    with pytest.raises(KeyError):
        parse_spot_exchange_info(payload, fetched_at=_FIXED_TIME)
