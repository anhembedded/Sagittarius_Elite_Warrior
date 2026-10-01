"""`EPIC-021J` §2.1 — the fake Futures account's orders. A resting order
placed appears in `open_orders()`; canceled, it does not. Still not a
matching engine: a resting order never fills.

`EPIC-028E` — every accepted order is also remembered in `history`, with a
real timestamp, for `GET /fapi/v1/allOrders`.

`EPIC-028O` — a `MARKET` order fills at once against the fixed book
(`futures_account_state.py`): it answers `FILLED`, never rests, is remembered
as filled, books one trade for `GET /fapi/v1/userTrades` and moves the
position and wallet `positionRisk` and `account` report. A reduce-only order
that would open or add to a position is refused with Binance's `-2022`; one
larger than the position closes it, reporting the capped fill in
`executedQty` while `origQty` stays what was sent.

`EPIC-028R` — conditional orders live apart, in `algo` (Binance's Algo Order
API); `move_price` triggers the ones a price crosses, placing their regular
orders here.
"""

from __future__ import annotations

import itertools
from decimal import Decimal
from typing import Any

from .futures_account_state import FuturesAccountState, FuturesFill
from .futures_algo_orders import FuturesAlgoOrders
from .futures_symbol_config import FuturesSymbolConfig
from .history_log import HistoryLog, now_ms

_STATUS_NEW = "NEW"
_STATUS_CANCELED = "CANCELED"
_STATUS_FILLED = "FILLED"
_TYPE_MARKET = "MARKET"

#: Binance's refusal of a reduce-only order that would not reduce.
_REDUCE_ONLY_REJECTED = (
    400,
    {"code": -2022, "msg": "ReduceOnly Order is rejected."},
)


class OrderBookState:
    """One instance per `run_binance_fake_server()` call — state does not
    outlive a single test's `with` block."""

    def __init__(self) -> None:
        self._orders: dict[str, dict[str, Any]] = {}
        self._order_ids = itertools.count(1_000_000)
        self.history = HistoryLog()
        #: `EPIC-028F` — the account's leverage and margin mode per symbol,
        #: carried here because this is the one state the Futures routes get.
        self.symbol_config = FuturesSymbolConfig()
        #: `EPIC-028O` — the wallet and positions market fills move.
        self.account = FuturesAccountState(self.symbol_config)
        self._trade_ids = itertools.count(5_000_000)
        #: `EPIC-028R` — the account's conditional orders.
        self.algo = FuturesAlgoOrders()

    def move_price(self, symbol: str, price: Decimal) -> None:
        """`EPIC-028R` — the market trades at `price`: every conditional
        order it crosses triggers and places its regular order."""
        self.algo.trigger(symbol, price, self.place)

    def place(self, params: dict[str, str]) -> tuple[int, dict[str, Any]]:
        """@brief Accepts one order from `POST /fapi/v1/order`'s
        form-encoded params: a `MARKET` order fills, anything else rests.
        @return `(status, body)`: the acknowledgement, or Binance's refusal."""
        client_order_id = params["newClientOrderId"]
        order = {
            "orderId": next(self._order_ids),
            "symbol": params["symbol"],
            "status": _STATUS_NEW,
            "clientOrderId": client_order_id,
            "price": params.get("price", "0"),
            "avgPrice": "0",
            "origQty": params["quantity"],
            "executedQty": "0",
            "cumQuote": "0",
            "type": params["type"],
            "side": params["side"],
            "positionSide": params.get("positionSide", "BOTH"),
            "stopPrice": params.get("stopPrice", "0"),
            "timeInForce": params.get("timeInForce", "GTC"),
            "reduceOnly": str(params.get("reduceOnly", "False")).lower() == "true",
        }
        placed_at = now_ms()
        if order["type"] == _TYPE_MARKET:
            quantity = self._market_quantity(order)
            if quantity is None:
                return _REDUCE_ONLY_REJECTED
            fill = self.account.fill_market(order["symbol"], order["side"], quantity)
            # `origQty` stays what was sent; a capped reduce-only fill shows
            # only in `executedQty` (PR #304 review, finding 3).
            order.update(
                status=_STATUS_FILLED,
                executedQty=str(quantity),
                avgPrice=str(fill.price),
                cumQuote=str(fill.price * fill.quantity),
            )
            self._remember_trade(order, fill, placed_at)
        else:
            self._orders[client_order_id] = order
        self.history.remember_order(
            {**order, "time": placed_at, "updateTime": placed_at}
        )
        return 200, order

    def _market_quantity(self, order: dict[str, Any]) -> Decimal | None:
        """The quantity a market order fills: as asked, or capped at the
        position for a reduce-only one; `None` when a reduce-only order
        would not reduce."""
        asked = Decimal(order["origQty"])
        if not order["reduceOnly"]:
            return asked
        held = self.account.position_amount(order["symbol"])
        reduces = held < 0 if order["side"] == "BUY" else held > 0
        if not reduces:
            return None
        return min(asked, abs(held))

    def _remember_trade(
        self, order: dict[str, Any], fill: FuturesFill, at_ms: int
    ) -> None:
        self.history.remember_trade(
            {
                "symbol": order["symbol"],
                "id": next(self._trade_ids),
                "orderId": order["orderId"],
                "side": order["side"],
                "price": str(fill.price),
                "qty": str(fill.quantity),
                "realizedPnl": f"{fill.realized_pnl:.8f}",
                "quoteQty": str(fill.price * fill.quantity),
                "commission": f"{fill.commission:.8f}",
                "commissionAsset": "USDT",
                "time": at_ms,
                "positionSide": "BOTH",
                "buyer": order["side"] == "BUY",
                "maker": False,
            }
        )

    def cancel(
        self, symbol: str, client_order_id: str | None, order_id: str | None
    ) -> dict[str, Any] | None:
        """@brief Removes and returns the matching order, or `None` if
        nothing open matches — the caller turns that into Binance's real
        `-2011 Unknown order sent` shape, not this module's job."""
        match_id = client_order_id
        if match_id is None and order_id is not None:
            match_id = next(
                (
                    cid
                    for cid, order in self._orders.items()
                    if str(order["orderId"]) == str(order_id)
                ),
                None,
            )
        order = self._orders.get(match_id) if match_id else None
        if order is None or order["symbol"] != symbol:
            return None
        del self._orders[match_id]
        self.history.mark_canceled(match_id)
        return {**order, "status": _STATUS_CANCELED}

    def cancel_all(self, symbol: str) -> None:
        for client_order_id in [
            cid for cid, order in self._orders.items() if order["symbol"] == symbol
        ]:
            del self._orders[client_order_id]
            self.history.mark_canceled(client_order_id)

    def open_orders(self, symbol: str | None) -> list[dict[str, Any]]:
        return [
            order
            for order in self._orders.values()
            if symbol is None or order["symbol"] == symbol
        ]
