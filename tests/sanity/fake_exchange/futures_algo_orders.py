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
modelled: `TRIGGERING`, `FINISHED`, trailing stops and the user data stream's
`ALGO_UPDATE`.

`EPIC-039L` — `closePosition=true` (a close-all stop, `STOP_MARKET` or
`TAKE_PROFIT_MARKET` only) is sent with **no quantity and no `reduceOnly`**; the
fake refuses both beside it, as the New Algo Order page says. When it triggers it
closes the whole position of the symbol on its side, as a reduce-only market
order. What Binance's pages do not say (`DECISION_2026-10-16` T1 to T3) is a switch
here, off by default, so a journey can run each answer:

  · `reject_without_position` — a close-all stop is refused when the symbol is flat;
  · `hold_triggers` — no order triggers (a stop that is late or missing);
  · `expire_when_flat` — one is `EXPIRED` ("canceled by the system") when the
    position goes to zero;
  · a trigger with no position on its side does nothing and the order `EXPIRED`s.
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
_EXPIRED = "EXPIRED"
_CLOSE_POSITION_TYPES = frozenset({"STOP_MARKET", "TAKE_PROFIT_MARKET"})
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

    def __init__(
        self,
        held: Callable[[str], Decimal] = lambda _symbol: Decimal(0),
        publish: Callable[[dict[str, Any], str | None], None] = lambda _o, _i: None,
        peek_order_id: Callable[[], int] = lambda: 0,
    ) -> None:
        self._orders: dict[str, dict[str, Any]] = {}
        self._algo_ids = itertools.count(2_000_000)
        #: The signed position of a symbol, for the close-all stops (`EPIC-039L`).
        self._held = held
        #: `ALGO_UPDATE` on the user-data stream: the order, and the id of the regular order it
        #: placed (once triggered). A triggered order is announced **before** the order it
        #: placed trades, so the app can link the fill to it (`DECISION_2026-10-16` T5 asks the
        #: owner for the real order).
        self._publish = publish
        self._peek_order_id = peek_order_id
        self.reject_without_position = False
        self.expire_when_flat = False
        #: No conditional order triggers: the exchange's stop is missing or late, so a test can
        #: show the bot's own exit working alone.
        self.hold_triggers = False

    def place(self, params: dict[str, str]) -> tuple[int, dict[str, Any]]:
        order_type = params.get("type", "")
        if params.get("algoType") != "CONDITIONAL" or order_type not in _PLACES:
            return _refusal(-1116, "Invalid orderType.")
        if "triggerPrice" not in params:
            return _refusal(-1102, "Mandatory parameter 'triggerPrice' was not sent.")
        close_position = str(params.get("closePosition", "false")).lower() == "true"
        refusal = self._refused_close_position(params, order_type, close_position)
        if refusal is not None:
            return refusal
        client_algo_id = params["clientAlgoId"]
        # "A unique id among open orders" (New Algo Order, 2026-10-16): an id that ended is free.
        held = self._orders.get(client_algo_id)
        if held is not None and held["algoStatus"] == _NEW:
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
            "quantity": "0" if close_position else params["quantity"],
            "closePosition": close_position,
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
        self._publish(order, None)
        return 200, dict(order)

    def _refused_close_position(
        self, params: dict[str, str], order_type: str, close_position: bool
    ) -> tuple[int, dict[str, Any]] | None:
        """Binance's refusals of a close-all stop (`closePosition` page, `EPIC-039L`)."""
        if not close_position:
            if "quantity" in params:
                return None
            return _refusal(-1102, "Mandatory parameter 'quantity' was not sent.")
        if order_type not in _CLOSE_POSITION_TYPES:
            return _refusal(-1116, "Invalid orderType.")
        if "quantity" in params:
            return _refusal(-1106, "Parameter 'quantity' sent when not required.")
        if "reduceOnly" in params:
            return _refusal(-1106, "Parameter 'reduceOnly' sent when not required.")
        if self.reject_without_position and self._held(params["symbol"]) == 0:
            return _refusal(-2022, "ReduceOnly Order is rejected.")
        return None

    def after_position_change(self, symbol: str) -> None:
        """A position of `symbol` changed: with `expire_when_flat`, the exchange cancels a
        close-all stop of a symbol that is flat ("canceled by the system")."""
        if not self.expire_when_flat or self._held(symbol) != 0:
            return
        for order in self._orders.values():
            if (
                order["symbol"] == symbol
                and order["closePosition"]
                and order["algoStatus"] == _NEW
            ):
                order.update(algoStatus=_EXPIRED, updateTime=now_ms())
                self._publish(order, None)

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
        self._publish(order, None)
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
        if self.hold_triggers:
            return
        for order in list(self._orders.values()):
            if order["symbol"] != symbol or order["algoStatus"] != _NEW:
                continue
            if not _crossed(order, price):
                continue
            if order["closePosition"]:
                self._trigger_close_position(order, place_order)
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
            self._place_triggered(order, place_order, params)

    def _trigger_close_position(
        self, order: dict[str, Any], place_order: PlaceOrder
    ) -> None:
        """A close-all stop closes the whole position of its side, reduce-only; with
        none on that side nothing happens and the order is `EXPIRED`."""
        held = self._held(order["symbol"])
        closes = held > 0 if order["side"] == "SELL" else held < 0
        if not closes:
            order.update(algoStatus=_EXPIRED, updateTime=now_ms())
            self._publish(order, None)
            return
        self._place_triggered(
            order,
            place_order,
            {
                "symbol": order["symbol"],
                "side": order["side"],
                "type": "MARKET",
                "quantity": str(abs(held)),
                "newClientOrderId": f"algo-{order['algoId']}",
                "positionSide": order["positionSide"],
                "reduceOnly": "True",
            },
        )

    def _place_triggered(
        self, order: dict[str, Any], place_order: PlaceOrder, params: dict[str, str]
    ) -> None:
        """The order has triggered: it is announced as `TRIGGERED` with the id of the regular
        order it places, then that order is placed (so the app links the fill to it)."""
        expected = self._peek_order_id()
        triggered_at = now_ms()
        order.update(
            algoStatus=_TRIGGERED,
            actualOrderId=str(expected),
            triggerTime=triggered_at,
            updateTime=triggered_at,
        )
        self._publish(order, str(expected))
        status, _ = place_order(params)
        if status != 200:
            order.update(algoStatus=_CANCELED, actualOrderId="", updateTime=now_ms())
            self._publish(order, None)

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
