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
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

#: Binance's own row limit when `limit` is not sent (500) and its maximum (1000).
_DEFAULT_LIMIT = 500
_MAX_LIMIT = 1000


#: How far the exchange's clock is from this machine's, in milliseconds
#: (`BUG-189`): negative when the machine runs fast. Binance's clock is its
#: own; every timestamp the fake stamps and every `/time` it answers is on it.
_clock_skew_ms = 0


def now_ms() -> int:
    """The exchange's clock, which is the machine's unless a test skews it."""
    return int(time.time() * 1000) + _clock_skew_ms


@contextmanager
def exchange_clock_skewed_by(skew_ms: int) -> Iterator[None]:
    """The exchange's clock reads `skew_ms` away from this machine's inside
    the block: `-90_000` is a machine whose clock runs 90 s fast."""
    global _clock_skew_ms
    before = _clock_skew_ms
    _clock_skew_ms = skew_ms
    try:
        yield
    finally:
        _clock_skew_ms = before


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

    def mark_filled(
        self, client_order_id: str, executed_qty: str, quote_qty: str
    ) -> None:
        """`EPIC-028O` — a resting order (a triggered stop-limit) that filled
        after it was placed."""
        order = self._orders.get(client_order_id)
        if order is not None:
            order.update(
                status="FILLED",
                executedQty=executed_qty,
                cummulativeQuoteQty=quote_qty,
                updateTime=now_ms(),
            )

    def remember_trade(self, trade: dict[str, Any]) -> None:
        self._trades.append(trade)

    def orders(
        self, query: HistoryQuery, *, purge_unfilled_after_ms: int | None = None
    ) -> list[dict[str, Any]]:
        """@param purge_unfilled_after_ms `EPIC-028Q` — Binance's Futures
        rule: a CANCELED or EXPIRED order with no fill, created longer ago
        than this, is no longer returned. `None` (Spot) keeps every order."""
        rows = [
            order
            for order in self._orders.values()
            if order["symbol"] == query.symbol
            and query.covers(order["time"])
            and not _purged(order, purge_unfilled_after_ms)
        ]
        return rows[: query.limit]

    def income(self, start_ms: int, end_ms: int, limit: int) -> list[dict[str, Any]]:
        """`EPIC-028Q` — `GET /fapi/v1/income`: one COMMISSION row per fill in
        the span, every symbol, the shape Binance documents."""
        rows = [
            {
                "symbol": trade["symbol"],
                "incomeType": "COMMISSION",
                "income": f"-{trade['commission']}",
                "asset": trade.get("commissionAsset", "USDT"),
                "time": trade["time"],
                "tranId": trade["id"],
            }
            for trade in self._trades
            if start_ms <= trade["time"] <= end_ms
        ]
        return rows[: min(limit, _MAX_LIMIT)]

    def trades(self, query: HistoryQuery) -> list[dict[str, Any]]:
        rows = [
            trade
            for trade in self._trades
            if trade["symbol"] == query.symbol and query.covers(trade["time"])
        ]
        return rows[: query.limit]


def _purged(order: dict[str, Any], purge_unfilled_after_ms: int | None) -> bool:
    if purge_unfilled_after_ms is None:
        return False
    unfilled = float(order.get("executedQty", "0")) == 0
    ended = order.get("status") in {"CANCELED", "EXPIRED"}
    return unfilled and ended and now_ms() - order["time"] > purge_unfilled_after_ms
