"""`EPIC-021H` — Binance Futures User Data Stream payload → domain types.

@details Deliberately its own module, not a reuse of
`futures_order_payload_mapper.py`'s reverse mapper: the REST order
response (`clientOrderId`, `side`, `type`, `origQty`, ...) and the stream
payload (`c`, `S`, `o`, `q`, ... nested one level under `"o"`) are
different wire shapes for the same concept — Binance's own stream
protocol uses short single-letter keys throughout, not the REST field
names. Pure parsing, no network — testable against static fixtures taken
from Binance's own documented `ORDER_TRADE_UPDATE`/`ACCOUNT_UPDATE`
payload shapes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.trading.client_order_id import ClientOrderId
from Sagittarius_Elite_Warrior.src.domain.trading.order import Order
from Sagittarius_Elite_Warrior.src.domain.trading.order_status import OrderStatus
from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
from Sagittarius_Elite_Warrior.src.domain.trading.time_in_force import TimeInForce
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide

#: The `"e"` (event type) field Binance stamps on every message this
#: stream cares about.
ORDER_TRADE_UPDATE = "ORDER_TRADE_UPDATE"
ACCOUNT_UPDATE = "ACCOUNT_UPDATE"

#: `"x"` (current execution type) value meaning this update represents an
#: actual trade/fill, not merely a status transition (e.g. a plain `NEW`
#: acknowledgement carries `x="NEW"`, not `"TRADE"`).
_TRADE_EXECUTION_TYPE = "TRADE"


def _decimal_or_none(raw: Any) -> Decimal | None:
    if raw is None:
        return None
    value = Decimal(str(raw))
    return value if value != 0 else None


def parse_order_trade_update(payload: dict[str, Any]) -> Order:
    """@brief Parses one `ORDER_TRADE_UPDATE` message's `"o"` object into
    a domain `Order` — the exchange's own account of this order's current
    state, always trusted over whatever this app last believed
    (`EPIC-021H` §2.4)."""
    o = payload["o"]
    time_in_force_raw = o.get("f")
    order_time_raw = o.get("T")
    return Order(
        client_order_id=ClientOrderId(o["c"]),
        symbol=o["s"],
        side=OrderSide[o["S"]],
        order_type=OrderType[o["o"]],
        quantity=Decimal(str(o["q"])),
        status=OrderStatus[o["X"]],
        price=_decimal_or_none(o.get("p")),
        stop_price=_decimal_or_none(o.get("sp")),
        time_in_force=(TimeInForce(time_in_force_raw) if time_in_force_raw else None),
        reduce_only=bool(o.get("R", False)),
        order_time=(
            datetime.fromtimestamp(order_time_raw / 1000, tz=UTC)
            if order_time_raw
            else None
        ),
    )


def is_fill_execution(payload: dict[str, Any]) -> bool:
    """@brief Whether this `ORDER_TRADE_UPDATE` represents an actual fill
    (partial or complete) rather than a plain status transition (`NEW`,
    `CANCELED`, `EXPIRED`, ...)."""
    return payload["o"].get("x") == _TRADE_EXECUTION_TYPE


def fill_details(payload: dict[str, Any]) -> tuple[Decimal, Decimal]:
    """@brief `(fill_price, fill_quantity)` for *this* fill event —
    Binance's `"L"`/`"l"` (last-filled price/quantity), not the order's
    running totals (`"ap"`/`"z"`), matching `OrderFilledEvent`'s own
    contract (`EPIC-021E`).
    @raise KeyError if called on a payload `is_fill_execution()` says is
    not a fill — callers must check that first.
    """
    o = payload["o"]
    return Decimal(str(o["L"])), Decimal(str(o["l"]))


def account_update_changed_symbols(payload: dict[str, Any]) -> list[str]:
    """@brief Every symbol one `ACCOUNT_UPDATE` reports a position change
    for — including one that went flat (`positionAmt` now `0`), which is
    itself a real change (a closed position), not something to filter out.
    @details Deliberately does not attempt to build a `LivePosition` from
    this payload: it omits `markPrice`/`leverage`/`liquidationPrice`
    entirely, so fabricating those fields as zero/unknown would misrepresent
    partial data as a complete snapshot. The caller re-fetches the
    authoritative position via `ITradingClient.get_positions(symbol)`
    instead (`EPIC-021H` §2.4 — the exchange's REST response is the
    source of truth, not a partial streamed hint).
    """
    return [position["s"] for position in payload.get("a", {}).get("P", [])]
