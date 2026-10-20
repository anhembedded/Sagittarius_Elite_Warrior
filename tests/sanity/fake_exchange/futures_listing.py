"""`EPIC-037E` — the fake Futures exchange's listing: the `exchangeInfo` payload, and the
filters the order checks read from the same payload (`futures_order_filters.py`).

@details One table, so the filters the fake advertises are the filters it enforces: a test
cannot see a tick size in `exchangeInfo` that `POST /fapi/v1/order` then ignores (`BUG-147`,
`CS-007`).
"""

from __future__ import annotations

from . import futures_market

#: Futures `/fapi/v1/exchangeInfo` payload — genuinely different shape from
#: spot's (`quantityPrecision`/`pricePrecision` at the symbol level, and
#: `MIN_NOTIONAL`'s value under `"notional"` rather than spot's
#: `"minNotional"`). Real filter values now included (`EPIC-021C`) so
#: `futures_metadata_parser`/`FuturesMetadataProvider` have a real payload
#: shape to round-trip against, not just `get_available_symbols()`.
FUTURES_EXCHANGE_INFO = {
    "timezone": "UTC",
    "serverTime": 0,
    "symbols": [
        {
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
                {"filterType": "MIN_NOTIONAL", "notional": "100"},
            ],
        },
        {
            "symbol": "ETHUSDT",
            "status": "TRADING",
            "pricePrecision": 2,
            "quantityPrecision": 2,
            "filters": [
                {
                    "filterType": "PRICE_FILTER",
                    "minPrice": "39.86",
                    "maxPrice": "306177",
                    "tickSize": "0.01",
                },
                {
                    "filterType": "LOT_SIZE",
                    "minQty": "0.01",
                    "maxQty": "10000",
                    "stepSize": "0.01",
                },
                {"filterType": "MIN_NOTIONAL", "notional": "20"},
            ],
        },
    ],
}

#: `EPIC-029J` J1b — the crowd symbols list like `BTCUSDT` (`futures_market.CROWD_SYMBOLS`).
_BTC_ROW = FUTURES_EXCHANGE_INFO["symbols"][0]
FUTURES_EXCHANGE_INFO["symbols"] += [
    {**_BTC_ROW, "symbol": symbol} for symbol in futures_market.CROWD_SYMBOLS
]
