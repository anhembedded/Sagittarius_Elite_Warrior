"""`EPIC-027J` — every Spot REST route this application's adapters (and the
future `EPIC-027K` order path) call, verified by reading `python-binance`'s
`client.py` directly (not assumed from Binance's public docs):

    GET    /api/v3/ping             `Client()` construction ping
    GET    /api/v3/time             clock-offset sync (`SpotSessionFactory`)
    GET    /api/v3/exchangeInfo     `market_metadata_parser.py` (real parser)
    GET    /api/v3/klines           spot kline fetch (`EPIC-027A`)
    GET    /api/v3/account          `get_account()` — balances
    GET    /api/v3/openOrders       `get_open_orders()`
    GET    /api/v3/allOrders        `get_all_orders()` (`EPIC-028E`)
    GET    /api/v3/myTrades         `get_my_trades()` (`EPIC-028E`)
    POST   /api/v3/order/test       `create_test_order()`
    POST   /api/v3/order            `create_order()` (`EPIC-027K`)
    DELETE /api/v3/order            `cancel_order()`
    DELETE /api/v3/openOrders       `cancel_all_open_orders()`
    POST   /api/v3/userDataStream   `stream_get_listen_key()` — unsigned
    PUT    /api/v3/userDataStream   `stream_keepalive()` — unsigned
    DELETE /api/v3/userDataStream   `stream_close()` — unsigned

Both `PUBLIC_API_VERSION` and `PRIVATE_API_VERSION` are `"v3"` in this
library version, so every one of these — signed or not — resolves under
`/api/v3/...`; there is no `/api/v1/` split the way Futures has `/fapi/v1/`
versus `/fapi/v3/positionRisk`.

Order lifecycle and balances are the only stateful part (`SpotAccountState`)
— a second, independent state object from Futures' `OrderBookState`
(`EPIC-027J`'s own design note: "Spot and Futures accounts are different
facts, never a union of both"). Everything else here is a fixed,
deterministic dict, same discipline as `futures_routes.py`.
"""

from __future__ import annotations

from .history_log import HistoryQuery
from .spot_account_state import SpotAccountState

#: `EPIC-027J` — real Spot-shaped `exchangeInfo`: `baseAsset`/`quoteAsset`
#: at the symbol level (not Futures' `pricePrecision`/`quantityPrecision`),
#: and the *current* Binance filter name `NOTIONAL`/`minNotional` (not the
#: legacy `MIN_NOTIONAL`/`notional` Futures still reports) — verified against
#: `market_metadata_parser.py`'s own docstring example, the real parser this
#: application already uses to read this exact payload.
_SPOT_EXCHANGE_INFO = {
    "timezone": "UTC",
    "serverTime": 0,
    "symbols": [
        {
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
                    "filterType": "NOTIONAL",
                    "minNotional": "5.00000000",
                    "applyToMarket": True,
                },
            ],
        },
        {
            "symbol": "ETHUSDT",
            "status": "TRADING",
            "baseAsset": "ETH",
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
                    "minQty": "0.0001",
                    "maxQty": "90000.00000000",
                    "stepSize": "0.0001",
                },
                {
                    "filterType": "NOTIONAL",
                    "minNotional": "5.00000000",
                    "applyToMarket": True,
                },
            ],
        },
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

#: `EPIC-021H` never validates this key's contents — it round-trips it back
#: unchanged on `PUT`. Distinct string from Futures' own fixed key, so a
#: test can prove which stream the fixture actually answered.
_FAKE_LISTEN_KEY = "fake-spot-listen-key-000000000000000000000000000000000000"

#: `path -> fixed response body`, `GET` only. `/api/v3/account` and
#: `/api/v3/openOrders` are excluded — both need live `SpotAccountState`,
#: so `_handle_get` answers them directly instead of from this static map.
GET_ROUTES: dict[str, object] = {
    "/api/v3/ping": {},
    "/api/v3/exchangeInfo": _SPOT_EXCHANGE_INFO,
    "/api/v3/klines": [_SPOT_KLINE_ROW],
    "/api/v3/time": {"serverTime": 0},
}


def handle(
    method: str, path: str, params: dict[str, str], state: SpotAccountState
) -> tuple[int, object] | None:
    """@brief Routes one already-parsed Spot request to its response.
    @return `(status_code, body)`, or `None` if this module does not
    recognize `method`+`path` — the caller (`server.py`) turns that into
    the fixture's real 404, never a guessed success.
    """
    if method == "GET":
        return _handle_get(path, params, state)
    if method == "POST":
        return _handle_post(path, params, state)
    if method == "PUT":
        return _handle_put(path)
    if method == "DELETE":
        return _handle_delete(path, params, state)
    return None


def _handle_get(
    path: str, params: dict[str, str], state: SpotAccountState
) -> tuple[int, object] | None:
    if path in GET_ROUTES:
        return 200, GET_ROUTES[path]
    if path == "/api/v3/account":
        return 200, {
            "makerCommission": 10,
            "takerCommission": 10,
            "buyerCommission": 0,
            "sellerCommission": 0,
            "canTrade": True,
            "canWithdraw": True,
            "canDeposit": True,
            "balances": state.account_balances(),
        }
    if path == "/api/v3/openOrders":
        return 200, state.open_orders(params.get("symbol"))
    if path in {"/api/v3/allOrders", "/api/v3/myTrades"}:
        return _history(path, HistoryQuery.parse(params), state)
    return None


#: Binance's Spot limit on `endTime - startTime` for both history endpoints.
_SPOT_HISTORY_SPAN_MS = 24 * 60 * 60 * 1000


def _history(
    path: str, query: HistoryQuery, state: SpotAccountState
) -> tuple[int, object]:
    if query.end_ms - query.start_ms > _SPOT_HISTORY_SPAN_MS:
        # Binance's real refusal for this exact case.
        return 400, {
            "code": -1127,
            "msg": "More than 24 hours between startTime and endTime.",
        }
    if path == "/api/v3/allOrders":
        return 200, state.history.orders(query)
    return 200, state.history.trades(query)


def _handle_post(
    path: str, params: dict[str, str], state: SpotAccountState
) -> tuple[int, object] | None:
    if path == "/api/v3/order/test":
        # `create_test_order()` — the exchange checks the payload but never
        # queues anything, so nothing here touches `state`. Real Binance's
        # own success body is an empty object.
        return 200, {}
    if path == "/api/v3/order":
        return 200, state.place(params)
    if path == "/api/v3/userDataStream":
        return 200, {"listenKey": _FAKE_LISTEN_KEY}
    return None


def _handle_put(path: str) -> tuple[int, object] | None:
    if path == "/api/v3/userDataStream":
        return 200, {}
    return None


def _handle_delete(
    path: str, params: dict[str, str], state: SpotAccountState
) -> tuple[int, object] | None:
    if path == "/api/v3/order":
        canceled = state.cancel(
            symbol=params.get("symbol", ""),
            client_order_id=params.get("origClientOrderId"),
            order_id=params.get("orderId"),
        )
        if canceled is None:
            # Binance's real shape for this exact failure — verified against
            # `binance.exceptions.BinanceAPIException`'s own parsing (a JSON
            # body carrying `code`/`msg`, non-2xx status) — same shape
            # `futures_routes.py` already relies on for the same failure.
            return 400, {"code": -2011, "msg": "Unknown order sent."}
        return 200, canceled
    if path == "/api/v3/openOrders":
        return 200, state.cancel_all(params.get("symbol", ""))
    if path == "/api/v3/userDataStream":
        return 200, {}
    return None
