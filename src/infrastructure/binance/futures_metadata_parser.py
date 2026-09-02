"""Parser for Binance USD-M Futures `/fapi/v1/exchangeInfo` symbol metadata
into pure domain entities (`EPIC-021C`).

@details Same shelf as `market_metadata_parser.py` (`BOT-095E1`) — same
abstraction level, both parsers of an exchange payload — but genuinely
different content: futures adds `quantityPrecision`/`pricePrecision` at the
symbol level, and its `MIN_NOTIONAL` filter carries the value under
`"notional"`, not spot's `"minNotional"`.

**Verification note** (`EPIC-021A`'s own disclosure applies here too): this
shape is written from Binance's documented futures `exchangeInfo` schema,
not re-verified against a live call — this sandbox's egress to every
`*.binance.*` domain is policy-blocked (confirmed on 6 hosts, `EPIC-021A`
§2.2b). Defensive parsing (missing filter -> named default, never a crash)
is the mitigation: an unexpected real payload degrades a symbol's metadata
to a conservative default rather than raising during boot.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.entities.futures_symbol_metadata import (
    FuturesSymbolMetadata,
)


class FuturesFilterType(str, Enum):
    """Binance USD-M Futures exchange filter type names."""

    PRICE_FILTER = "PRICE_FILTER"
    LOT_SIZE = "LOT_SIZE"
    MIN_NOTIONAL = "MIN_NOTIONAL"


class FuturesMetadataKey(str, Enum):
    """JSON dictionary field keys in Binance futures `exchangeInfo`
    payloads."""

    SYMBOLS = "symbols"
    SYMBOL = "symbol"
    STATUS = "status"
    QUANTITY_PRECISION = "quantityPrecision"
    PRICE_PRECISION = "pricePrecision"
    FILTERS = "filters"
    FILTER_TYPE = "filterType"
    TICK_SIZE = "tickSize"
    STEP_SIZE = "stepSize"
    #: Futures' `MIN_NOTIONAL` filter carries the value under `"notional"` —
    #: unlike spot's, which uses `"minNotional"`. Both are accepted
    #: defensively below, in case a future API revision changes this.
    NOTIONAL = "notional"
    MIN_NOTIONAL = "minNotional"


DEFAULT_STATUS: str = "TRADING"
DEFAULT_TICK_SIZE = Decimal("0.01")
DEFAULT_STEP_SIZE = Decimal("0.001")
DEFAULT_MIN_NOTIONAL = Decimal(5)
DEFAULT_QUANTITY_PRECISION = 3
DEFAULT_PRICE_PRECISION = 2


def _decimal_from(value: object, default: Decimal) -> Decimal:
    """`Decimal(str(x))`, never `Decimal(float)` — constructing straight from
    a `float` reproduces its binary-fraction imprecision before the
    `Decimal` even starts (`0.1` -> `Decimal('0.1000000000000000055511151231257827021181583404541015625')`).
    Binance's own JSON already sends these as strings; `str()` here only
    guards a payload that, contrary to spec, sent one as a raw number."""
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except (ArithmeticError, ValueError):
        return default


def parse_futures_symbol_metadata(
    symbol_info: dict[str, Any],
    fetched_at: datetime | None = None,
) -> FuturesSymbolMetadata:
    """Parses a single symbol info dictionary from Binance's futures
    `/fapi/v1/exchangeInfo`.

    Example structure:
    {
        "symbol": "BTCUSDT",
        "status": "TRADING",
        "pricePrecision": 2,
        "quantityPrecision": 3,
        "filters": [
            {"filterType": "PRICE_FILTER", "minPrice": "556.80", "maxPrice": "4529764", "tickSize": "0.10"},
            {"filterType": "LOT_SIZE", "minQty": "0.001", "maxQty": "1000", "stepSize": "0.001"},
            {"filterType": "MIN_NOTIONAL", "notional": "5"}
        ]
    }
    """
    symbol = str(symbol_info.get(FuturesMetadataKey.SYMBOL.value, "")).upper()
    status = str(
        symbol_info.get(FuturesMetadataKey.STATUS.value, DEFAULT_STATUS)
    ).upper()
    timestamp = fetched_at or datetime.now(UTC)

    filters = symbol_info.get(FuturesMetadataKey.FILTERS.value, [])
    filter_map: dict[str, dict[str, Any]] = {}
    for raw_filter in filters:
        if not isinstance(raw_filter, dict):
            continue
        filter_type = raw_filter.get(FuturesMetadataKey.FILTER_TYPE.value)
        if isinstance(filter_type, str):
            filter_map[filter_type] = raw_filter

    price_filter = filter_map.get(FuturesFilterType.PRICE_FILTER.value, {})
    tick_size = _decimal_from(
        price_filter.get(FuturesMetadataKey.TICK_SIZE.value), DEFAULT_TICK_SIZE
    )

    lot_size_filter = filter_map.get(FuturesFilterType.LOT_SIZE.value, {})
    step_size = _decimal_from(
        lot_size_filter.get(FuturesMetadataKey.STEP_SIZE.value), DEFAULT_STEP_SIZE
    )

    min_notional_filter = filter_map.get(FuturesFilterType.MIN_NOTIONAL.value, {})
    min_notional_raw = min_notional_filter.get(
        FuturesMetadataKey.NOTIONAL.value,
        min_notional_filter.get(FuturesMetadataKey.MIN_NOTIONAL.value),
    )
    min_notional = _decimal_from(min_notional_raw, DEFAULT_MIN_NOTIONAL)

    quantity_precision = symbol_info.get(FuturesMetadataKey.QUANTITY_PRECISION.value)
    price_precision = symbol_info.get(FuturesMetadataKey.PRICE_PRECISION.value)

    return FuturesSymbolMetadata(
        symbol=symbol,
        status=status,
        step_size=step_size,
        tick_size=tick_size,
        min_notional=min_notional,
        quantity_precision=(
            int(quantity_precision)
            if isinstance(quantity_precision, int)
            else DEFAULT_QUANTITY_PRECISION
        ),
        price_precision=(
            int(price_precision)
            if isinstance(price_precision, int)
            else DEFAULT_PRICE_PRECISION
        ),
        fetched_at=timestamp,
    )


def parse_futures_exchange_info(
    payload: dict[str, Any],
    fetched_at: datetime | None = None,
) -> list[FuturesSymbolMetadata]:
    """Parses every symbol entry in a full futures `exchangeInfo` response.
    A malformed individual entry (not a dict) is skipped rather than
    aborting the whole catalog."""
    timestamp = fetched_at or datetime.now(UTC)
    symbols = payload.get(FuturesMetadataKey.SYMBOLS.value, [])
    return [
        parse_futures_symbol_metadata(entry, fetched_at=timestamp)
        for entry in symbols
        if isinstance(entry, dict)
    ]
