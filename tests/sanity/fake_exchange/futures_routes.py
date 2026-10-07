"""`EPIC-021J` — every Futures Testnet REST route this application's
adapters actually call, verified by reading `python-binance`'s
`client.py` directly (not assumed from Binance's public docs, which do
not always match a given library version's exact path/version number):

    GET    /fapi/v1/ping            Client() construction ping (`BUG-045`)
    GET    /fapi/v1/time            `FuturesAccountReader.check_connection()`
    GET    /fapi/v1/exchangeInfo    `FuturesMetadataProvider` (`EPIC-021C`)
    GET    /fapi/v1/klines          futures kline fetch (`EPIC-021A`); `interval=1s`
                                    is Binance's -1120, Futures has no 1s klines
    GET    /fapi/v2/account         `futures_account()` — version 2
    GET    /fapi/v1/positionSide/dual  hedge-mode check (`EPIC-021D`)
    POST   /fapi/v1/order/test      `futures_create_test_order()` (`EPIC-021F`)
    POST   /fapi/v1/order           `futures_create_order()` (`EPIC-021G`)
    DELETE /fapi/v1/order           `futures_cancel_order()`
    DELETE /fapi/v1/allOpenOrders   `futures_cancel_all_open_orders()`
    GET    /fapi/v1/openOrders      `futures_get_open_orders()`
    GET    /fapi/v1/allOrders       `futures_get_all_orders()` (`EPIC-028E`)
    GET    /fapi/v1/userTrades      `futures_account_trades()` (`EPIC-028E`)
    GET    /fapi/v1/income          `futures_income_history()` (`EPIC-028Q`)
    GET    /fapi/v3/positionRisk    `futures_position_information()` — **version
                                      3**, not the v2 this task's own design
                                      draft assumed; `client.py`'s
                                      `_request_futures_api("get",
                                      "positionRisk", True, 3, ...)` is the
                                      actual source of truth (`EPIC-021J`
                                      §6.1 implementation notes).
    POST   /fapi/v1/leverage        `futures_change_leverage()` (`EPIC-028F`)
    POST   /fapi/v1/marginType      `futures_change_margin_type()` (`EPIC-028F`)
    GET    /fapi/v1/commissionRate  `futures_commission_rate()` (`EPIC-028F`)
    GET    /fapi/v1/symbolConfig    `futures_symbol_config()` (`EPIC-028O`)
    GET    /fapi/v1/leverageBracket `futures_leverage_bracket()` (`EPIC-028O`)
    GET    /fapi/v1/premiumIndex    `futures_mark_price()` (`EPIC-028O`)
    GET    /fapi/v1/ticker/bookTicker  `futures_orderbook_ticker()` (`EPIC-028O`)
    GET    /fapi/v1/multiAssetsMargin  `futures_get_multi_assets_mode()` (`EPIC-028O`)
    POST   /fapi/v1/algoOrder       `futures_create_algo_order()` (`EPIC-028R`)
    GET    /fapi/v1/algoOrder       `futures_get_algo_order()` (`EPIC-028R`)
    GET    /fapi/v1/openAlgoOrders  `futures_get_open_algo_orders()` (`EPIC-028R`)
    GET    /fapi/v1/allAlgoOrders   `futures_get_all_algo_orders()` (`EPIC-028R`)
    DELETE /fapi/v1/algoOrder       `futures_cancel_algo_order()` (`EPIC-028R`)
    DELETE /fapi/v1/algoOpenOrders  `futures_cancel_all_algo_open_orders()` (`EPIC-028R`)
    POST   /fapi/v1/listenKey       `futures_stream_get_listen_key()` (`EPIC-021H`)
    PUT    /fapi/v1/listenKey       `futures_stream_keepalive()` (`EPIC-021H`)

Order lifecycle, the per-symbol leverage and margin mode
(`OrderBookState.symbol_config`) and, since `EPIC-028O`, the wallet and
positions market fills move (`OrderBookState.account`, which `account` and
`positionRisk` report) are the stateful parts — everything else here
is a fixed, deterministic dict, same discipline as the original
`binance_fake_server.py`.
"""

from __future__ import annotations

from . import futures_market
from .history_log import HistoryQuery, now_ms
from .order_book_state import OrderBookState

#: `EPIC-027A` — one fixed row, distinguishable from `spot_routes.py`'s own
#: row by `open_price`, so a test can prove a `MarketType.FUTURES_USD_M`
#: request actually reached `/fapi/v1/klines` and not `/api/v3/klines`. One
#: row is still fewer than any page-size `limit` python-binance requests, so
#: pagination still stops after this one page instead of looping.
_FUTURES_KLINE_ROW = [
    1672531200000,
    "222.0",
    "224.0",
    "220.0",
    "223.0",
    "20.0",
    1672531259999,
    "4460.0",
    8,
    "10.0",
    "2230.0",
    "0",
]

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

#: `EPIC-021H` never validates this key's contents — it round-trips it back
#: unchanged on `PUT`. A fixed string is enough to prove the stream adapter
#: calls the right two endpoints in the right order.
_FAKE_LISTEN_KEY = "fake-listen-key-0000000000000000000000000000000000000000"

#: `path -> fixed response body`, `GET` only.
GET_ROUTES: dict[str, object] = {
    "/fapi/v1/ping": {},
    "/fapi/v1/exchangeInfo": _FUTURES_EXCHANGE_INFO,
    "/fapi/v1/klines": [_FUTURES_KLINE_ROW],
    "/fapi/v1/time": {"serverTime": 0},
    "/fapi/v1/positionSide/dual": {"dualSidePosition": False},
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
    if path == "/fapi/v1/klines" and params.get("interval") == "1s":
        # Binance's own answer: USDⓈ-M Futures, testnet and mainnet alike, has no
        # 1-second klines (`BUG-172`).
        return 400, {"code": -1120, "msg": "Invalid interval."}
    if path in GET_ROUTES:
        return 200, GET_ROUTES[path]
    if path == "/fapi/v1/openOrders":
        return 200, state.open_orders(params.get("symbol"))
    if path == "/fapi/v2/account":
        return 200, state.account.account()
    if path == "/fapi/v3/positionRisk":
        return 200, state.account.position_risk(params.get("symbol"))
    if path == "/fapi/v1/multiAssetsMargin":
        return 200, {"multiAssetsMargin": state.account.multi_assets}
    if path in {
        "/fapi/v1/allOrders",
        "/fapi/v1/userTrades",
        "/fapi/v1/income",
        "/fapi/v1/allAlgoOrders",
    }:
        return _history(path, params, state)
    if path == "/fapi/v1/algoOrder":
        return state.algo.get(params)
    if path == "/fapi/v1/openAlgoOrders":
        return 200, state.algo.open_orders(params.get("symbol"))
    if path == "/fapi/v1/commissionRate":
        return 200, {
            "symbol": params.get("symbol", ""),
            "makerCommissionRate": "0.0002",
            "takerCommissionRate": "0.0005",
        }
    if path == "/fapi/v1/symbolConfig":
        return state.symbol_config.symbol_config(params)
    if path == "/fapi/v1/leverageBracket":
        return futures_market.leverage_bracket(params.get("symbol", ""))
    if path == "/fapi/v1/premiumIndex":
        return futures_market.premium_index(params.get("symbol", ""))
    if path == "/fapi/v1/ticker/bookTicker":
        return futures_market.book_ticker(params.get("symbol", ""))
    return None


#: `EPIC-028Q` — Binance's Futures limit on `endTime - startTime` for the
#: history endpoints, and how long it keeps an unfilled cancelled order.
_FUTURES_HISTORY_SPAN_MS = 7 * 24 * 60 * 60 * 1000
_FUTURES_UNFILLED_ORDER_KEPT_MS = 3 * 24 * 60 * 60 * 1000


def _history(
    path: str, params: dict[str, str], state: OrderBookState
) -> tuple[int, object]:
    start = int(params.get("startTime", 0))
    end = int(params.get("endTime", now_ms()))
    if "startTime" in params and end - start > _FUTURES_HISTORY_SPAN_MS:
        # The Spot routes' refusal shape, with Futures' seven days.
        return 400, {
            "code": -1127,
            "msg": "More than 7 days between startTime and endTime.",
        }
    if path == "/fapi/v1/income":
        return 200, state.history.income(start, end, int(params.get("limit", 100)))
    query = HistoryQuery.parse(params)
    if path == "/fapi/v1/allAlgoOrders":
        return 200, state.algo.all_orders(query)
    if path == "/fapi/v1/allOrders":
        return 200, state.history.orders(
            query, purge_unfilled_after_ms=_FUTURES_UNFILLED_ORDER_KEPT_MS
        )
    return 200, state.history.trades(query)


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
        return state.place(params)
    if path == "/fapi/v1/algoOrder":
        return state.algo.place(params)
    if path == "/fapi/v1/listenKey":
        return 200, {"listenKey": _FAKE_LISTEN_KEY}
    if path == "/fapi/v1/leverage":
        return state.symbol_config.change_leverage(params)
    if path == "/fapi/v1/marginType":
        return state.symbol_config.change_margin_type(params)
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
    if path == "/fapi/v1/algoOrder":
        return state.algo.cancel(params)
    if path == "/fapi/v1/algoOpenOrders":
        return state.algo.cancel_all(params.get("symbol", ""))
    if path == "/fapi/v1/allOpenOrders":
        state.cancel_all(params.get("symbol", ""))
        return 200, {
            "code": 200,
            "msg": "The operation of cancel all open order is done.",
        }
    return None
