"""Unit tests for Binance exchangeInfo symbol metadata parser (BOT-095E1)."""

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.infrastructure.binance.market_metadata_parser import (
    DEFAULT_APPLY_TO_MARKET,
    DEFAULT_MIN_NOTIONAL,
    parse_binance_symbol_metadata,
)


def test_parse_binance_symbol_metadata():
    raw_payload = {
        "symbol": "BTCUSDT",
        "status": "TRADING",
        "baseAsset": "BTC",
        "quoteAsset": "USDT",
        "filters": [
            {
                "filterType": "PRICE_FILTER",
                "minPrice": "0.01000000",
                "maxPrice": "1000000.00000000",
                "tickSize": "0.01000000",
            },
            {
                "filterType": "LOT_SIZE",
                "minQty": "0.00001000",
                "maxQty": "9000.00000000",
                "stepSize": "0.00001000",
            },
            {
                "filterType": "NOTIONAL",
                "minNotional": "5.00000000",
                "applyToMarket": True,
            },
        ],
    }
    now = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
    meta = parse_binance_symbol_metadata(raw_payload, fetched_at=now)

    assert meta.symbol == "BTCUSDT"
    assert meta.status == "TRADING"
    assert meta.base_asset == "BTC"
    assert meta.quote_asset == "USDT"
    assert meta.fetched_at == now

    assert meta.price_filter.min_price == 0.01
    assert meta.price_filter.max_price == 1000000.0
    assert meta.price_filter.tick_size == 0.01

    assert meta.lot_size_filter.min_qty == 0.00001
    assert meta.lot_size_filter.max_qty == 9000.0
    assert meta.lot_size_filter.step_size == 0.00001

    assert meta.notional_filter.min_notional == 5.0
    assert meta.notional_filter.apply_to_market is True


def test_parse_skips_a_filter_object_that_carries_no_filter_type():
    """EPIC-002D: a filter with no `filterType` is dropped, not stored.

    It used to be kept under a `None` key, which no lookup in the parser can
    reach — every one passes a real filter-type string. The entry was therefore
    unreadable, and the map claimed a filter it could not serve. Dropping it
    leaves the parsed result identical, which is what this asserts: the two
    well-formed filters still parse, and the third falls back to its defaults.
    """
    raw_payload = {
        "symbol": "ETHUSDT",
        "filters": [
            {"minPrice": "0.50000000"},  # no filterType — must be ignored
            {
                "filterType": "PRICE_FILTER",
                "minPrice": "0.01000000",
                "maxPrice": "500.00000000",
                "tickSize": "0.01000000",
            },
            {
                "filterType": "LOT_SIZE",
                "minQty": "0.00100000",
                "maxQty": "100.00000000",
                "stepSize": "0.00100000",
            },
        ],
    }

    meta = parse_binance_symbol_metadata(raw_payload)

    assert meta.price_filter.min_price == 0.01  # not 0.50 from the typeless one
    assert meta.lot_size_filter.min_qty == 0.001
    # NOTIONAL was absent entirely, so the documented defaults stand.
    assert meta.notional_filter.min_notional == DEFAULT_MIN_NOTIONAL
    assert meta.notional_filter.apply_to_market is DEFAULT_APPLY_TO_MARKET
