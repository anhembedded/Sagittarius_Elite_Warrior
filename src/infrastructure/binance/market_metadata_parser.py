"""Parser for Binance exchangeInfo symbol metadata into pure domain entities (BOT-095E1)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.entities.symbol_market_metadata import (
    LotSizeFilter,
    NotionalFilter,
    PriceFilter,
    SymbolMarketMetadata,
)


class BinanceFilterType(str, Enum):
    """Binance exchange filter type names."""

    PRICE_FILTER = "PRICE_FILTER"
    LOT_SIZE = "LOT_SIZE"
    NOTIONAL = "NOTIONAL"
    MIN_NOTIONAL = "MIN_NOTIONAL"


class BinanceMetadataKey(str, Enum):
    """JSON dictionary field keys in Binance exchangeInfo payloads."""

    SYMBOL = "symbol"
    STATUS = "status"
    BASE_ASSET = "baseAsset"
    QUOTE_ASSET = "quoteAsset"
    FILTERS = "filters"
    FILTER_TYPE = "filterType"
    MIN_PRICE = "minPrice"
    MAX_PRICE = "maxPrice"
    TICK_SIZE = "tickSize"
    MIN_QTY = "minQty"
    MAX_QTY = "maxQty"
    STEP_SIZE = "stepSize"
    MIN_NOTIONAL = "minNotional"
    NOTIONAL = "notional"
    APPLY_TO_MARKET = "applyToMarket"


DEFAULT_STATUS: str = "TRADING"
DEFAULT_MIN_PRICE: float = 0.01
DEFAULT_MAX_PRICE: float = 1_000_000.0
DEFAULT_TICK_SIZE: float = 0.01
DEFAULT_MIN_QTY: float = 0.00001
DEFAULT_MAX_QTY: float = 1_000_000.0
DEFAULT_STEP_SIZE: float = 0.00001
DEFAULT_MIN_NOTIONAL: float = 5.0
DEFAULT_APPLY_TO_MARKET: bool = True


def parse_binance_symbol_metadata(
    symbol_info: dict[str, Any],
    fetched_at: datetime | None = None,
) -> SymbolMarketMetadata:
    """Parses a single symbol info dictionary from Binance API /exchangeInfo.

    Example structure:
    {
        "symbol": "BTCUSDT",
        "status": "TRADING",
        "baseAsset": "BTC",
        "quoteAsset": "USDT",
        "filters": [
            {"filterType": "PRICE_FILTER", "minPrice": "0.01", "maxPrice": "1000000.0", "tickSize": "0.01"},
            {"filterType": "LOT_SIZE", "minQty": "0.00001", "maxQty": "9000.0", "stepSize": "0.00001"},
            {"filterType": "NOTIONAL", "minNotional": "5.00000000", "applyToMarket": True}
        ]
    }
    """
    symbol = str(symbol_info.get(BinanceMetadataKey.SYMBOL.value, "")).upper()
    status = str(
        symbol_info.get(BinanceMetadataKey.STATUS.value, DEFAULT_STATUS)
    ).upper()
    base_asset = str(symbol_info.get(BinanceMetadataKey.BASE_ASSET.value, "")).upper()
    quote_asset = str(symbol_info.get(BinanceMetadataKey.QUOTE_ASSET.value, "")).upper()
    timestamp = fetched_at or datetime.now(UTC)

    filters = symbol_info.get(BinanceMetadataKey.FILTERS.value, [])
    # Annotated rather than inferred: without it every `filter_map.get()` below
    # is `Any`, and the one call that omits a default (`NOTIONAL`) widens to
    # `Any | None` and reaches `float()` unchecked.
    #
    # The `filterType` guard is what the annotation then forced into the open: a
    # filter object arriving without that key used to be stored under a `None`
    # key. Nothing could ever read it back -- every lookup below passes a real
    # string -- so dropping it changes no behaviour, it just stops the map from
    # claiming a filter it cannot serve.
    filter_map: dict[str, dict[str, Any]] = {}
    for raw_filter in filters:
        if not isinstance(raw_filter, dict):
            continue
        filter_type = raw_filter.get(BinanceMetadataKey.FILTER_TYPE.value)
        if isinstance(filter_type, str):
            filter_map[filter_type] = raw_filter

    # Price Filter
    pf_data = filter_map.get(BinanceFilterType.PRICE_FILTER.value, {})
    price_filter = PriceFilter(
        min_price=float(
            pf_data.get(BinanceMetadataKey.MIN_PRICE.value, DEFAULT_MIN_PRICE)
        ),
        max_price=float(
            pf_data.get(BinanceMetadataKey.MAX_PRICE.value, DEFAULT_MAX_PRICE)
        ),
        tick_size=float(
            pf_data.get(BinanceMetadataKey.TICK_SIZE.value, DEFAULT_TICK_SIZE)
        ),
    )

    # Lot Size Filter
    ls_data = filter_map.get(BinanceFilterType.LOT_SIZE.value, {})
    lot_size_filter = LotSizeFilter(
        min_qty=float(ls_data.get(BinanceMetadataKey.MIN_QTY.value, DEFAULT_MIN_QTY)),
        max_qty=float(ls_data.get(BinanceMetadataKey.MAX_QTY.value, DEFAULT_MAX_QTY)),
        step_size=float(
            ls_data.get(BinanceMetadataKey.STEP_SIZE.value, DEFAULT_STEP_SIZE)
        ),
    )

    # Notional Filter (Binance uses NOTIONAL or MIN_NOTIONAL)
    notional_data = filter_map.get(BinanceFilterType.NOTIONAL.value) or filter_map.get(
        BinanceFilterType.MIN_NOTIONAL.value, {}
    )
    min_notional_raw = notional_data.get(
        BinanceMetadataKey.MIN_NOTIONAL.value,
        notional_data.get(BinanceMetadataKey.NOTIONAL.value, DEFAULT_MIN_NOTIONAL),
    )
    notional_filter = NotionalFilter(
        min_notional=float(min_notional_raw),
        apply_to_market=bool(
            notional_data.get(
                BinanceMetadataKey.APPLY_TO_MARKET.value, DEFAULT_APPLY_TO_MARKET
            )
        ),
    )

    return SymbolMarketMetadata(
        symbol=symbol,
        status=status,
        base_asset=base_asset,
        quote_asset=quote_asset,
        price_filter=price_filter,
        lot_size_filter=lot_size_filter,
        notional_filter=notional_filter,
        fetched_at=timestamp,
    )
