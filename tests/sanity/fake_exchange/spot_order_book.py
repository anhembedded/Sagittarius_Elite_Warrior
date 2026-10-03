"""`EPIC-029A` — the fake Spot exchange's resting orders, and which of them a
move of the last price makes trade.

@details Split out of `spot_account_state.py` (which owns balances, fills
and the user-data events) when a Grid's resting LIMIT orders needed to fill:
the account file was at the 400-line ratchet. The rules, all at the order's
own limit price, in full (no partial fills, as everywhere in this fake):

- a `LIMIT` buy trades once the last price is at or below its limit, a sell
  once it is at or above;
- a `STOP_LOSS_LIMIT` is first triggered when the last price crosses its
  stop (a buy at or above, a sell at or below), and then trades as a limit.

A limit placed already marketable rests until the next price move: this
fake has no taker fill for a limit (the real venue would fill it at once,
at the better price).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

_SIDE_BUY = "BUY"
_ORDER_TYPE_LIMIT = "LIMIT"
_ORDER_TYPE_STOP_LIMIT = "STOP_LOSS_LIMIT"


class SpotOrderBook:
    """Resting orders by client order id, as Binance stores them, plus the
    fake's private `_order_id` and `_triggered` keys."""

    def __init__(self) -> None:
        self._orders: dict[str, dict[str, Any]] = {}

    def rest(self, order: dict[str, Any], order_id: int) -> None:
        self._orders[order["clientOrderId"]] = {
            **order,
            "_order_id": order_id,
            "_triggered": False,
        }

    def take(
        self, symbol: str, client_order_id: str | None, order_id: str | None
    ) -> dict[str, Any] | None:
        """@brief Removes and returns the resting order on `symbol` matching
        the client order id, or else the exchange id; `None` when none
        does."""
        match_id = client_order_id
        if match_id is None and order_id is not None:
            match_id = next(
                (
                    cid
                    for cid, order in self._orders.items()
                    if str(order["_order_id"]) == str(order_id)
                ),
                None,
            )
        order = self._orders.get(match_id) if match_id else None
        if order is None or order["symbol"] != symbol:
            return None
        return self._orders.pop(order["clientOrderId"])

    def resting(self, symbol: str | None) -> list[dict[str, Any]]:
        return [
            order
            for order in self._orders.values()
            if symbol is None or order["symbol"] == symbol
        ]

    def trade_at(
        self, symbol: str, price: Decimal
    ) -> list[tuple[dict[str, Any], Decimal]]:
        """@brief Removes and returns every resting order on `symbol` that
        `price` makes trade, with the price it trades at (its limit)."""
        trading: list[tuple[dict[str, Any], Decimal]] = []
        for order in self.resting(symbol):
            limit = _trade_price(order, price)
            if limit is not None:
                del self._orders[order["clientOrderId"]]
                trading.append((order, limit))
        return trading


def _trade_price(order: dict[str, Any], price: Decimal) -> Decimal | None:
    buy = order["side"] == _SIDE_BUY
    if order["type"] == _ORDER_TYPE_STOP_LIMIT:
        stop = Decimal(order["stopPrice"])
        if price >= stop if buy else price <= stop:
            order["_triggered"] = True
        if not order["_triggered"]:
            return None
    elif order["type"] != _ORDER_TYPE_LIMIT:
        return None
    limit = Decimal(order["price"])
    return limit if (price <= limit if buy else price >= limit) else None
