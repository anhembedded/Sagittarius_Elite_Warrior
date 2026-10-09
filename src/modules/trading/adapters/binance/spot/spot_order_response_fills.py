"""`BOT-173` — the fills a Spot placement response carries.

@details `POST /api/v3/order` answers a MARKET order (and a LIMIT that crosses
the book) with its `status` and, for `newOrderRespType=FULL`, the `fills` that
made it: `price`, `qty`, `commission`, `commissionAsset` and `tradeId` each.
That is the exchange's own record of the trades, available the moment the
order returns and independent of the user-data stream, so the trading client
reports it (`IOrderFillReporter`) instead of waiting for the stream to say it
again. A fill whose `tradeId` is absent or unreadable cannot be counted once,
so it is not reported (`ResponseFill.trade_id` is required) and the caller is
told how many were left out.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass(frozen=True, slots=True)
class ResponseFill:
    """One trade of a placement response."""

    price: Decimal
    quantity: Decimal
    fee: tuple[Decimal, str] | None
    trade_id: int


@dataclass(frozen=True, slots=True)
class ResponseFills:
    """The countable fills of a response, and how many entries were not."""

    fills: tuple[ResponseFill, ...]
    unreadable: int = 0


def response_fills(payload: dict[str, Any]) -> ResponseFills:
    """@brief The fills of `payload`, in the order the exchange lists them."""
    readable: list[ResponseFill] = []
    unreadable = 0
    for entry in payload.get("fills") or ():
        fill = _fill_or_none(entry)
        if fill is None:
            unreadable += 1
        else:
            readable.append(fill)
    return ResponseFills(tuple(readable), unreadable)


def _fill_or_none(entry: object) -> ResponseFill | None:
    if not isinstance(entry, dict):
        return None
    try:
        trade_id = int(entry["tradeId"])
        if trade_id < 0:
            return None
        quantity = Decimal(str(entry["qty"]))
        if quantity <= 0:
            return None
        return ResponseFill(
            Decimal(str(entry["price"])),
            quantity,
            _fee_or_none(entry),
            trade_id,
        )
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return None


def _fee_or_none(entry: dict[str, Any]) -> tuple[Decimal, str] | None:
    amount, asset = entry.get("commission"), entry.get("commissionAsset")
    if amount is None or asset is None:
        return None
    return Decimal(str(amount)), str(asset)
