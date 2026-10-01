"""`EPIC-028R` — the fake Futures account's conditional orders: Binance's
USD-M Algo Order API, as `python-binance` 1.0.37 calls it.

    POST   /fapi/v1/algoOrder       `futures_create_algo_order()`
    GET    /fapi/v1/algoOrder       `futures_get_algo_order()`
    GET    /fapi/v1/openAlgoOrders  `futures_get_open_algo_orders()`
    GET    /fapi/v1/allAlgoOrders   `futures_get_all_algo_orders()`
    DELETE /fapi/v1/algoOrder       `futures_cancel_algo_order()`
    DELETE /fapi/v1/algoOpenOrders  `futures_cancel_all_algo_open_orders()`

An algo order rests as `NEW` until `OrderBookState.move_price` crosses its
trigger: a buy stop at or above, a sell stop at or below. It then becomes
`TRIGGERED`, and its regular order (a limit at its price, or a market order
for the `_MARKET` types) is placed in the order book; `actualOrderId` names
it. Answer shapes follow Binance's documentation of the Algo Order API; not
modelled: `TRIGGERING`, `FINISHED`, `EXPIRED`, trailing stops and the user
data stream's `ALGO_UPDATE`.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from .history_log import HistoryQuery, now_ms

_NEW = "NEW"
_CANCELED = "CANCELED"
_TRIGGERED = "TRIGGERED"
#: The conditional type → the regular order type it places when triggered.
_PLACES: dict[str, str] = {
    "STOP": "LIMIT",
    "TAKE_PROFIT": "LIMIT",
    "STOP_MARKET": "MARKET",
    "TAKE_PROFIT_MARKET": "MARKET",
}
#: Whether a buy of this type triggers when the price rises to it (a stop)
#: or falls to it (a take-profit); a sell is the other way round.
_BUY_TRIGGERS_ON_RISE = {"STOP": True, "STOP_MARKET": True}
_MAX_LIMIT = 100

#: Places a regular order from `POST /fapi/v1/order`-shaped params and
#: answers `(status, body)` — `OrderBookState.place`.
type PlaceOrder = Callable[[dict[str, str]], tuple[int, dict[str, Any]]]


def _refusal(code: int, msg: str) -> tuple[int, dict[str, Any]]:
    return 400, {"code": code, "msg": msg}


class FuturesAlgoOrders:
    """Every conditional order the fake account was sent, open or not."""

    def __init__(self) -> None:
        self._orders: dict[str, dict[str, Any]] = {}
        self._algo_ids = itertools.count(2_000_000)

    def place(self, params: dict[str, str]) -> tuple[int, dict[str, Any]]:
        order_type = params.get("type", "")
        if params.get("algoType") != "CONDITIONAL" or order_type not in _PLACES:
            return _refusal(-1116, "Invalid orderType.")
        if "triggerPrice" not in params:
            return _refusal(-1102, "Mandatory parameter 'triggerPrice' was not sent.")
        client_algo_id = params["clientAlgoId"]
        if client_algo_id in self._orders:
            return _refusal(-4116, "ClientOrderId is duplicated.")
        created = now_ms()
        order = {
            "algoId": next(self._algo_ids),
            "clientAlgoId": client_algo_id,
            "algoType": "CONDITIONAL",
            "orderType": order_type,
            "symbol": params["symbol"],
            "side": params["side"],
            "positionSide": params.get("positionSide", "BOTH"),
            "timeInForce": params.get("timeInForce", "GTC"),
            "quantity": params["quantity"],
            "algoStatus": _NEW,
            "triggerPrice": params["triggerPrice"],
            "price": params.get("price", "0"),
            "workingType": params.get("workingType", "CONTRACT_PRICE"),
            "reduceOnly": str(params.get("reduceOnly", "False")).lower() == "true",
            "actualOrderId": "",
            "createTime": created,
            "updateTime": created,
            "triggerTime": 0,
        }
        self._orders[client_algo_id] = order
        return 200, dict(order)

    def get(self, params: dict[str, str]) -> tuple[int, dict[str, Any]]:
        order = self._find(params)
        if order is None:
            return _refusal(-2013, "Order does not exist.")
        return 200, dict(order)

    def open_orders(self, symbol: str | None) -> list[dict[str, Any]]:
        return [
            dict(order)
            for order in self._orders.values()
            if order["algoStatus"] == _NEW and symbol in (None, order["symbol"])
        ]

    def all_orders(self, query: HistoryQuery) -> list[dict[str, Any]]:
        rows = [
            dict(order)
            for order in self._orders.values()
            if order["symbol"] == query.symbol and query.covers(order["createTime"])
        ]
        return rows[: min(query.limit, _MAX_LIMIT)]

    def cancel(self, params: dict[str, str]) -> tuple[int, dict[str, Any]]:
        order = self._find(params)
        if order is None or order["algoStatus"] != _NEW:
            return _refusal(-2011, "Unknown order sent.")
        order.update(algoStatus=_CANCELED, updateTime=now_ms())
        return 200, {
            "algoId": order["algoId"],
            "clientAlgoId": order["clientAlgoId"],
            "code": "200",
            "msg": "success",
        }

    def cancel_all(self, symbol: str) -> tuple[int, dict[str, Any]]:
        for order in self._orders.values():
            if order["symbol"] == symbol and order["algoStatus"] == _NEW:
                order.update(algoStatus=_CANCELED, updateTime=now_ms())
        return 200, {
            "code": 200,
            "msg": "The operation of cancel all open order is done.",
        }

    def trigger(self, symbol: str, price: Decimal, place_order: PlaceOrder) -> None:
        """Triggers every open conditional order on `symbol` that `price`
        crosses, placing its regular order through `place_order`."""
        for order in list(self._orders.values()):
            if order["symbol"] != symbol or order["algoStatus"] != _NEW:
                continue
            if not _crossed(order, price):
                continue
            regular_type = _PLACES[order["orderType"]]
            params = {
                "symbol": symbol,
                "side": order["side"],
                "type": regular_type,
                "quantity": order["quantity"],
                "newClientOrderId": f"algo-{order['algoId']}",
                "positionSide": order["positionSide"],
                "reduceOnly": str(order["reduceOnly"]),
            }
            if regular_type == "LIMIT":
                params.update(price=order["price"], timeInForce=order["timeInForce"])
            status, placed = place_order(params)
            if status != 200:
                order.update(algoStatus=_CANCELED, updateTime=now_ms())
                continue
            triggered_at = now_ms()
            order.update(
                algoStatus=_TRIGGERED,
                actualOrderId=str(placed["orderId"]),
                triggerTime=triggered_at,
                updateTime=triggered_at,
            )

    def _find(self, params: dict[str, str]) -> dict[str, Any] | None:
        client_algo_id = params.get("clientAlgoId")
        if client_algo_id is not None:
            order = self._orders.get(client_algo_id)
        else:
            algo_id = params.get("algoId")
            order = next(
                (o for o in self._orders.values() if str(o["algoId"]) == algo_id),
                None,
            )
        if order is None or order["symbol"] != params.get("symbol"):
            return None
        return order


def _crossed(order: dict[str, Any], price: Decimal) -> bool:
    trigger = Decimal(order["triggerPrice"])
    rises = _BUY_TRIGGERS_ON_RISE.get(order["orderType"], False)
    if order["side"] == "SELL":
        rises = not rises
    return price >= trigger if rises else price <= trigger
