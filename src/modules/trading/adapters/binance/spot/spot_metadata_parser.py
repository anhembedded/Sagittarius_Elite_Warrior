"""Parser for Binance Spot `GET /api/v3/exchangeInfo` symbol metadata into
`SymbolOrderMetadata` (`EPIC-027I`).

@details Same shelf as `futures_metadata_parser.py` — same abstraction
level, both parsers of an exchange payload — but a genuinely different
failure policy: Spot's `NOTIONAL` filter carries the value under
`"minNotional"` (unlike futures' `MIN_NOTIONAL`, which uses `"notional"`),
Spot publishes no `quantityPrecision`/`pricePrecision` at the symbol level,
and this parser **raises** on a missing required filter or field rather than
defaulting — the opposite of `futures_metadata_parser.py`'s
defensive-parsing policy (`EPIC-027I`'s own acceptance criterion). Futures'
existing, test-covered behaviour is unchanged by this file; only the new
Spot path is strict.

**Verification note** (`EPIC-021A`'s own disclosure applies here too): this
shape is written from Binance's documented Spot `exchangeInfo` schema, not
re-verified against a live call — this sandbox's egress to every
`*.binance.*` domain is policy-blocked (confirmed on 6 hosts, `EPIC-021A`
§2.2b).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)


class SpotFilterType(str, Enum):
    """Binance Spot exchange filter type names this parser reads."""

    PRICE_FILTER = "PRICE_FILTER"
    LOT_SIZE = "LOT_SIZE"
    MARKET_LOT_SIZE = "MARKET_LOT_SIZE"
    NOTIONAL = "NOTIONAL"


class SpotMetadataKey(str, Enum):
    """JSON dictionary field keys in Binance Spot `exchangeInfo` payloads."""

    SYMBOLS = "symbols"
    SYMBOL = "symbol"
    STATUS = "status"
    FILTERS = "filters"
    FILTER_TYPE = "filterType"
    TICK_SIZE = "tickSize"
    STEP_SIZE = "stepSize"
    #: Spot's `NOTIONAL` filter carries the value under `"minNotional"` —
    #: unlike futures' `MIN_NOTIONAL`, which uses `"notional"`.
    MIN_NOTIONAL = "minNotional"


DEFAULT_STATUS: str = "TRADING"


def _required_decimal(
    raw_filter: dict[str, Any], key: str, filter_type: str, symbol: str
) -> Decimal:
    """@raise KeyError `key` is missing from `raw_filter` — a genuinely
    malformed or unexpectedly-shaped Spot exchange filter, never silently
    defaulted (`code/errors.md` #6/#7; Spot has no default to fall back to,
    unlike `futures_metadata_parser._decimal_from()`)."""
    if key not in raw_filter:
        raise KeyError(
            f"Spot exchangeInfo symbol {symbol!r}: filter {filter_type!r} "
            f"is missing required field {key!r}"
        )
    return Decimal(str(raw_filter[key]))


def _filter_map(symbol_info: dict[str, Any]) -> dict[str, dict[str, Any]]:
    filters = symbol_info.get(SpotMetadataKey.FILTERS.value, [])
    result: dict[str, dict[str, Any]] = {}
    for raw_filter in filters:
        if not isinstance(raw_filter, dict):
            continue
        filter_type = raw_filter.get(SpotMetadataKey.FILTER_TYPE.value)
        if isinstance(filter_type, str):
            result[filter_type] = raw_filter
    return result


def _required_filter(
    filter_map: dict[str, dict[str, Any]], filter_type: SpotFilterType, symbol: str
) -> dict[str, Any]:
    """@raise KeyError `filter_type` is absent from the symbol's filter
    list entirely."""
    if filter_type.value not in filter_map:
        raise KeyError(
            f"Spot exchangeInfo symbol {symbol!r}: missing required filter "
            f"{filter_type.value!r}"
        )
    return filter_map[filter_type.value]


def parse_spot_symbol_metadata(
    symbol_info: dict[str, Any],
    fetched_at: datetime | None = None,
) -> SymbolOrderMetadata:
    """Parses a single symbol entry from Binance's Spot
    `GET /api/v3/exchangeInfo`.

    @raise KeyError `PRICE_FILTER`, `LOT_SIZE` or `NOTIONAL` is missing from
    the symbol's filter list, or one of their required fields is — Spot's
    exchange-rounding rules must come from the real payload, never a
    fabricated default (`code/errors.md` #6/#7, `EPIC-027I`'s own acceptance
    criterion). `MARKET_LOT_SIZE` is the one optional filter: when absent,
    `market_step_size` is `None` and `SymbolOrderMetadata.step_size_for()`
    falls back to `LOT_SIZE`'s own step.

    Example structure:
    {
        "symbol": "BTCUSDT",
        "status": "TRADING",
        "filters": [
            {"filterType": "PRICE_FILTER", "minPrice": "0.01", "maxPrice": "1000000", "tickSize": "0.01"},
            {"filterType": "LOT_SIZE", "minQty": "0.00001", "maxQty": "9000", "stepSize": "0.00001"},
            {"filterType": "MARKET_LOT_SIZE", "minQty": "0.00001", "maxQty": "100", "stepSize": "0.00001"},
            {"filterType": "NOTIONAL", "minNotional": "5", "applyToMarket": true}
        ]
    }
    """
    symbol = str(symbol_info.get(SpotMetadataKey.SYMBOL.value, "")).upper()
    status = str(symbol_info.get(SpotMetadataKey.STATUS.value, DEFAULT_STATUS)).upper()
    timestamp = fetched_at or datetime.now(UTC)

    filter_map = _filter_map(symbol_info)

    price_filter = _required_filter(filter_map, SpotFilterType.PRICE_FILTER, symbol)
    tick_size = _required_decimal(
        price_filter,
        SpotMetadataKey.TICK_SIZE.value,
        SpotFilterType.PRICE_FILTER.value,
        symbol,
    )

    lot_size_filter = _required_filter(filter_map, SpotFilterType.LOT_SIZE, symbol)
    step_size = _required_decimal(
        lot_size_filter,
        SpotMetadataKey.STEP_SIZE.value,
        SpotFilterType.LOT_SIZE.value,
        symbol,
    )

    market_lot_size_filter = filter_map.get(SpotFilterType.MARKET_LOT_SIZE.value)
    market_step_size = (
        _required_decimal(
            market_lot_size_filter,
            SpotMetadataKey.STEP_SIZE.value,
            SpotFilterType.MARKET_LOT_SIZE.value,
            symbol,
        )
        if market_lot_size_filter is not None
        else None
    )

    notional_filter = _required_filter(filter_map, SpotFilterType.NOTIONAL, symbol)
    min_notional = _required_decimal(
        notional_filter,
        SpotMetadataKey.MIN_NOTIONAL.value,
        SpotFilterType.NOTIONAL.value,
        symbol,
    )

    return SymbolOrderMetadata(
        symbol=symbol,
        status=status,
        step_size=step_size,
        tick_size=tick_size,
        min_notional=min_notional,
        quantity_precision=None,
        price_precision=None,
        fetched_at=timestamp,
        market_step_size=market_step_size,
    )


def parse_spot_exchange_info(
    payload: dict[str, Any],
    fetched_at: datetime | None = None,
) -> list[SymbolOrderMetadata]:
    """Parses every symbol entry in a full Spot `exchangeInfo` response.
    A malformed individual entry (not a dict) is skipped rather than
    aborting the whole catalog — mirrors `parse_futures_exchange_info`'s
    own per-entry defensiveness; only per-*filter* strictness is the new,
    Spot-specific behaviour (`EPIC-027I`)."""
    timestamp = fetched_at or datetime.now(UTC)
    symbols = payload.get(SpotMetadataKey.SYMBOLS.value, [])
    return [
        parse_spot_symbol_metadata(entry, fetched_at=timestamp)
        for entry in symbols
        if isinstance(entry, dict)
    ]
