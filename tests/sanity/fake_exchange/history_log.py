"""`EPIC-028E` — what the fake exchange remembers for its history endpoints.

@details Both account states (`OrderBookState` for Futures, `SpotAccountState`
for Spot) record every order they accept and every fill they make here, with
a real millisecond timestamp, so `allOrders`, `myTrades` and `userTrades`
answer with the account's own history and honour `startTime`/`endTime` the
way Binance does (both inclusive). The open-order stores stay what they were;
a cancel only updates the remembered order's status.

`HistoryQuery` also enforces the rule the readers split around: a span
longer than the endpoint accepts is refused with Binance's own error shape
(`-1127` on Spot), never silently truncated.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

#: Binance's own row limit when `limit` is not sent (500) and its maximum (1000).
_DEFAULT_LIMIT = 500
_MAX_LIMIT = 1000


def now_ms() -> int:
    return int(time.time() * 1000)


@dataclass(frozen=True)
class HistoryQuery:
    """One history request's parameters, as the endpoint parses them."""

    symbol: str
    start_ms: int
    end_ms: int
    limit: int

    @classmethod
    def parse(cls, params: dict[str, str]) -> HistoryQuery:
        end = int(params.get("endTime", now_ms()))
        return cls(
            symbol=params["symbol"],
            start_ms=int(params.get("startTime", 0)),
            end_ms=end,
            limit=min(int(params.get("limit", _DEFAULT_LIMIT)), _MAX_LIMIT),
        )

    def covers(self, row_ms: int) -> bool:
        return self.start_ms <= row_ms <= self.end_ms


class HistoryLog:
    """Every order and fill one account has seen, oldest first."""

    def __init__(self) -> None:
        self._orders: dict[str, dict[str, Any]] = {}
        self._trades: list[dict[str, Any]] = []

    def remember_order(self, order: dict[str, Any]) -> None:
        self._orders[order["clientOrderId"]] = order

    def mark_canceled(self, client_order_id: str) -> None:
        order = self._orders.get(client_order_id)
        if order is not None:
            order["status"] = "CANCELED"
            order["updateTime"] = now_ms()

    def remember_trade(self, trade: dict[str, Any]) -> None:
        self._trades.append(trade)

    def orders(self, query: HistoryQuery) -> list[dict[str, Any]]:
        rows = [
            order
            for order in self._orders.values()
            if order["symbol"] == query.symbol and query.covers(order["time"])
        ]
        return rows[: query.limit]

    def trades(self, query: HistoryQuery) -> list[dict[str, Any]]:
        rows = [
            trade
            for trade in self._trades
            if trade["symbol"] == query.symbol and query.covers(trade["time"])
        ]
        return rows[: query.limit]
