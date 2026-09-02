"""`EPIC-021J` — every Futures Testnet REST route this application's
adapters actually call, verified by reading `python-binance`'s
`client.py` directly (not assumed from Binance's public docs, which do
not always match a given library version's exact path/version number):

    GET    /fapi/v1/ping            Client() construction ping (`BUG-045`)
    GET    /fapi/v1/time            `FuturesAccountReader.check_connection()`
    GET    /fapi/v1/exchangeInfo    `FuturesMetadataProvider` (`EPIC-021C`)
    GET    /fapi/v1/klines          futures kline fetch (`EPIC-021A`)
    GET    /fapi/v2/account         `futures_account()` — version 2
    GET    /fapi/v1/positionSide/dual  hedge-mode check (`EPIC-021D`)
    POST   /fapi/v1/order/test      `futures_create_test_order()` (`EPIC-021F`)
    POST   /fapi/v1/order           `futures_create_order()` (`EPIC-021G`)
    DELETE /fapi/v1/order           `futures_cancel_order()`
    DELETE /fapi/v1/allOpenOrders   `futures_cancel_all_open_orders()`
    GET    /fapi/v1/openOrders      `futures_get_open_orders()`
    GET    /fapi/v3/positionRisk    `futures_position_information()` — **version
                                      3**, not the v2 this task's own design
                                      draft assumed; `client.py`'s
                                      `_request_futures_api("get",
                                      "positionRisk", True, 3, ...)` is the
                                      actual source of truth (`EPIC-021J`
                                      §6.1 implementation notes).
    POST   /fapi/v1/listenKey       `futures_stream_get_listen_key()` (`EPIC-021H`)
    PUT    /fapi/v1/listenKey       `futures_stream_keepalive()` (`EPIC-021H`)

Order lifecycle is the only stateful part (`OrderBookState`) — everything
else here is a fixed, deterministic dict, same discipline as the original
`binance_fake_server.py`.
"""

from __future__ import annotations

from typing import Any

from .order_book_state import OrderBookState

#: Futures `/fapi/v1/exchangeInfo` payload — genuinely different shape from
#: spot's (`quantityPrecision`/`pricePrecision` at the symbol level, and
#: `MIN_NOTIONAL`'s value under `"notional"` rather than spot's
#: `"minNotional"`). Real filter values now included (`EPIC-021C`) so
#: `futures_metadata_parser`/`FuturesMetadataProvider` have a real payload
#: shape to round-trip against, not just `get_available_symbols()`.
_FUTURES_EXCHANGE_INFO = {
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

#: `EPIC-021D` — a minimal, always-One-way, always-funded account snapshot.
#: `futures_account()` hits `/fapi/v2/account` (version 2, not 1 — verified
#: from `python-binance`'s own `_request_futures_api("get", "account", True,
#: 2, ...)` call, not assumed).
_FUTURES_ACCOUNT = {
    "assets": [{"asset": "USDT", "walletBalance": "15000.00000000"}],
    "positions": [],
}

#: Deliberately never populated by order placement (`order_book_state.py`'s
#: own docstring: no matching engine, no fills, no position tracking) — a
#: fixed, always-flat account. Any test needing a real open position sizes
#: its own fixture payload directly rather than expecting this fake to
#: derive one from an order.
_POSITION_RISK: list[dict[str, Any]] = []

#: `EPIC-021H` never validates this key's contents — it round-trips it back
#: unchanged on `PUT`. A fixed string is enough to prove the stream adapter
#: calls the right two endpoints in the right order.
_FAKE_LISTEN_KEY = "fake-listen-key-0000000000000000000000000000000000000000"

#: `path -> fixed response body`, `GET` only.
GET_ROUTES: dict[str, object] = {
    "/fapi/v1/ping": {},
    "/fapi/v1/exchangeInfo": _FUTURES_EXCHANGE_INFO,
    "/fapi/v1/klines": [],
    "/fapi/v1/time": {"serverTime": 0},
    "/fapi/v2/account": _FUTURES_ACCOUNT,
    "/fapi/v1/positionSide/dual": {"dualSidePosition": False},
    "/fapi/v3/positionRisk": _POSITION_RISK,
}


def handle(
    method: str, path: str, params: dict[str, str], state: OrderBookState
) -> tuple[int, object] | None:
    """@brief Routes one already-parsed request to its response.
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
    path: str, params: dict[str, str], state: OrderBookState
) -> tuple[int, object] | None:
    if path in GET_ROUTES:
        return 200, GET_ROUTES[path]
    if path == "/fapi/v1/openOrders":
        return 200, state.open_orders(params.get("symbol"))
    return None


def _handle_post(
    path: str, params: dict[str, str], state: OrderBookState
) -> tuple[int, object] | None:
    if path == "/fapi/v1/order/test":
        # `VALIDATE_ONLY` mode (`EPIC-021F`) — the exchange checks
        # signature/permissions/payload but never queues anything, so
        # nothing here touches `state`. Real Binance's own success body is
        # an empty object.
        return 200, {}
    if path == "/fapi/v1/order":
        return 200, state.place(params)
    if path == "/fapi/v1/listenKey":
        return 200, {"listenKey": _FAKE_LISTEN_KEY}
    return None


def _handle_put(path: str) -> tuple[int, object] | None:
    if path == "/fapi/v1/listenKey":
        return 200, {}
    return None


def _handle_delete(
    path: str, params: dict[str, str], state: OrderBookState
) -> tuple[int, object] | None:
    if path == "/fapi/v1/order":
        canceled = state.cancel(
            symbol=params.get("symbol", ""),
            client_order_id=params.get("origClientOrderId"),
            order_id=params.get("orderId"),
        )
        if canceled is None:
            # Binance's real shape for this exact failure — verified
            # against `binance.exceptions.BinanceAPIException`'s own
            # parsing (a JSON body carrying `code`/`msg`, non-2xx status).
            return 400, {"code": -2011, "msg": "Unknown order sent."}
        return 200, canceled
    if path == "/fapi/v1/allOpenOrders":
        state.cancel_all(params.get("symbol", ""))
        return 200, {
            "code": 200,
            "msg": "The operation of cancel all open order is done.",
        }
    return None
