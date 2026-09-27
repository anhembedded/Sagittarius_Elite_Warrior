"""`EPIC-021J` — the 3 spot `GET` routes this fixture has always served
(`EPIC-009` D6). No state, no futures — split out unchanged from the
original `binance_fake_server.py` so that file's growth (`EPIC-021J`
futures order lifecycle) stays under `architecture-rule.md` §5.4's
400-line guideline without touching this half at all.
"""

from __future__ import annotations

#: A tiny, fixed exchange-info payload — enough shape for
#: `get_available_symbols()` to parse successfully, not a realistic catalog.
_EXCHANGE_INFO = {
    "timezone": "UTC",
    "serverTime": 0,
    "symbols": [
        {"symbol": "BTCUSDT", "status": "TRADING"},
        {"symbol": "ETHUSDT", "status": "TRADING"},
    ],
}

#: `EPIC-027A` — one fixed row, distinguishable from `futures_routes.py`'s
#: own row by `open_price`, so a test can prove a `MarketType.SPOT` request
#: actually reached `/api/v3/klines` and not `/fapi/v1/klines`. One row is
#: still fewer than any page-size `limit` python-binance requests, so
#: `get_historical_klines_generator`'s pagination still stops after this
#: one page instead of looping (same reasoning the old empty list relied on).
_SPOT_KLINE_ROW = [
    1672531200000,
    "111.0",
    "112.0",
    "110.0",
    "111.5",
    "10.0",
    1672531259999,
    "1115.0",
    5,
    "5.0",
    "557.5",
    "0",
]

#: `path -> fixed response body`, `GET` only — spot has never needed a
#: signed or stateful call in this application.
GET_ROUTES: dict[str, object] = {
    "/api/v3/ping": {},
    "/api/v3/exchangeInfo": _EXCHANGE_INFO,
    "/api/v3/klines": [_SPOT_KLINE_ROW],
}
