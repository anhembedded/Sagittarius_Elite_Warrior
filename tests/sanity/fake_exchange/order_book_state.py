"""`EPIC-021J` §2.1 — the one piece of mutable state this fake server
keeps: which orders are currently open. Deliberately not a matching
engine — no fills, no position tracking, no price simulation. An order
placed appears in `open_orders()`; canceled, it does not. That is the
entire lifecycle `EPIC-021D`-`H`'s adapters need a fake to exercise;
anything more would be a second implementation of Binance's real matching
engine, with its own bugs to maintain.
"""

from __future__ import annotations

import itertools
from typing import Any

_STATUS_NEW = "NEW"
_STATUS_CANCELED = "CANCELED"


class OrderBookState:
    """One instance per `run_binance_fake_server()` call — state does not
    outlive a single test's `with` block."""

    def __init__(self) -> None:
        self._orders: dict[str, dict[str, Any]] = {}
        self._order_ids = itertools.count(1_000_000)

    def place(self, params: dict[str, str]) -> dict[str, Any]:
        """@brief Stores a new `NEW` order from `POST /fapi/v1/order`'s
        form-encoded params and returns the acknowledgement payload."""
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
            "type": params["type"],
            "side": params["side"],
            "positionSide": params.get("positionSide", "BOTH"),
            "stopPrice": params.get("stopPrice", "0"),
            "timeInForce": params.get("timeInForce", "GTC"),
            "reduceOnly": str(params.get("reduceOnly", "False")).lower() == "true",
        }
        self._orders[client_order_id] = order
        return order

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
        return {**order, "status": _STATUS_CANCELED}

    def cancel_all(self, symbol: str) -> None:
        for client_order_id in [
            cid for cid, order in self._orders.items() if order["symbol"] == symbol
        ]:
            del self._orders[client_order_id]

    def open_orders(self, symbol: str | None) -> list[dict[str, Any]]:
        return [
            order
            for order in self._orders.values()
            if symbol is None or order["symbol"] == symbol
        ]
