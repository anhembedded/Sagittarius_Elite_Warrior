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

#: `path -> fixed response body`, `GET` only — spot has never needed a
#: signed or stateful call in this application.
GET_ROUTES: dict[str, object] = {
    "/api/v3/ping": {},
    "/api/v3/exchangeInfo": _EXCHANGE_INFO,
    # Empty on purpose: this tier proves resolution and wiring, not kline
    # data — an empty page terminates get_historical_klines_generator's
    # pagination immediately instead of looping.
    "/api/v3/klines": [],
}
