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
    UNREAD_SPOT_FILTERS,
    SpotFilterType,
    parse_spot_exchange_info,
    parse_spot_symbol_metadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType

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


def test_a_zero_market_lot_size_step_leaves_market_step_size_none():
    """`BUG-138` — Binance's own convention for `MARKET_LOT_SIZE`: a
    `"0.00000000"` `stepSize`/`minQty` means "no restriction from this
    filter, apply `LOT_SIZE` instead", not "a step of exactly zero".
    Confirmed live against Binance Spot Testnet's real `BTCUSDT`
    `exchangeInfo` (`GET /api/v3/exchangeInfo?symbol=BTCUSDT`), which
    reports exactly this shape. Treating `Decimal("0")` as a real,
    present step (the bug this test guards) made
    `SymbolOrderMetadata.step_size_for(OrderType.MARKET)` return `0`;
    `OrderQuantityRoundingPolicy.round_quantity_down()` and the payload
    mapper's own `_require_step_aligned()` both treat `step_size <= 0` as
    "no filter to round against" and skip rounding entirely — so an
    unrounded MARKET SELL quantity (e.g. a BUY's fill net of its fee) was
    sent straight to the exchange and rejected with a real
    `-1013 Filter failure: LOT_SIZE`, exactly what the user's own
    EPIC-027P AC5 run hit."""
    entry = {
        "symbol": "BTCUSDT",
        "status": "TRADING",
        "filters": [
            f for f in _BTCUSDT_ENTRY["filters"] if f["filterType"] != "MARKET_LOT_SIZE"
        ]
        + [
            {
                "filterType": "MARKET_LOT_SIZE",
                "minQty": "0.00000000",
                "maxQty": "105.07867116",
                "stepSize": "0.00000000",
            }
        ],
    }

    metadata = parse_spot_symbol_metadata(entry, fetched_at=_FIXED_TIME)

    assert metadata.market_step_size is None
    assert metadata.step_size_for(order_type=OrderType.MARKET) == metadata.step_size


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


def test_reads_the_percent_price_by_side_band_when_published():
    """`BUG-147` — Binance rejects a BUY or SELL priced outside this band
    (`-1013 Filter failure: PERCENT_PRICE_BY_SIDE`); the bot checks a plan
    against it only if the parser carries it."""
    entry = {
        **_BTCUSDT_ENTRY,
        "filters": [
            *_BTCUSDT_ENTRY["filters"],
            {
                "filterType": "PERCENT_PRICE_BY_SIDE",
                "bidMultiplierUp": "5",
                "bidMultiplierDown": "0.2",
                "askMultiplierUp": "5",
                "askMultiplierDown": "0.2",
                "avgPriceMins": 5,
            },
        ],
    }

    band = parse_spot_symbol_metadata(entry, fetched_at=_FIXED_TIME).price_band

    assert band is not None
    assert (band.bid_down, band.bid_up) == (Decimal("0.2"), Decimal(5))
    assert (band.ask_down, band.ask_up) == (Decimal("0.2"), Decimal(5))


def test_no_band_when_the_symbol_publishes_none():
    metadata = parse_spot_symbol_metadata(_BTCUSDT_ENTRY, fetched_at=_FIXED_TIME)

    assert metadata.price_band is None


#: Binance's documented Spot symbol filters (Spot API, "Filters").
_BINANCE_SPOT_FILTERS = (
    "PRICE_FILTER",
    "PERCENT_PRICE",
    "PERCENT_PRICE_BY_SIDE",
    "LOT_SIZE",
    "MIN_NOTIONAL",
    "NOTIONAL",
    "ICEBERG_PARTS",
    "MARKET_LOT_SIZE",
    "MAX_NUM_ORDERS",
    "MAX_NUM_ALGO_ORDERS",
    "MAX_NUM_ICEBERG_ORDERS",
    "MAX_POSITION",
    "TRAILING_DELTA",
    "T_PLUS_SELL",
    "MAX_NUM_ORDER_LISTS",
    "MAX_NUM_ORDER_AMENDS",
)


def test_every_spot_filter_is_read_or_declared_unread():
    """`BUG-147` (CS-007) — `PERCENT_PRICE_BY_SIDE` was published, never read,
    and reached the user as `-1013`. Every documented filter is now either
    read (`SpotFilterType`) or named with a reason (`UNREAD_SPOT_FILTERS`).

    Retire when: Binance publishes no symbol filters."""
    read = {member.value for member in SpotFilterType}
    missing = [
        name
        for name in _BINANCE_SPOT_FILTERS
        if name not in read and name not in UNREAD_SPOT_FILTERS
    ]
    assert missing == []
    assert not read & set(UNREAD_SPOT_FILTERS)


def test_a_filter_nobody_declared_is_logged_once_by_name(caplog):
    entry = {
        **_BTCUSDT_ENTRY,
        "filters": [*_BTCUSDT_ENTRY["filters"], {"filterType": "NEW_RULE"}],
    }
    payload = {"symbols": [entry, {**entry, "symbol": "ETHUSDT"}]}

    with caplog.at_level("WARNING", logger="App.SpotMetadata"):
        parse_spot_exchange_info(payload, fetched_at=_FIXED_TIME)

    warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1
    assert "NEW_RULE" in warnings[0]
