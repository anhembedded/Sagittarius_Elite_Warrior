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
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.infrastructure.binance.order_enum_parsing import (
    order_status_or_unknown,
    order_type_or_unknown,
    time_in_force_or_none,
)

#: The `"e"` (event type) field Binance stamps on every message this
#: stream cares about.
ORDER_TRADE_UPDATE = "ORDER_TRADE_UPDATE"
ACCOUNT_UPDATE = "ACCOUNT_UPDATE"

#: `"x"` (current execution type) value meaning this update represents an
#: actual trade/fill, not merely a status transition (e.g. a plain `NEW`
#: acknowledgement carries `x="NEW"`, not `"TRADE"`).
_TRADE_EXECUTION_TYPE = "TRADE"

#: The asset this app ever trades in — the only entry
#: `account_update_wallet_balance` reads out of a potentially multi-asset
#: `"a"."B"` array (`EPIC-021M` §2.2).
_QUOTE_ASSET = "USDT"


def _decimal_or_none(raw: Any) -> Decimal | None:
    if raw is None:
        return None
    value = Decimal(str(raw))
    return value if value != 0 else None


def parse_order_trade_update(payload: dict[str, Any]) -> Order:
    """@brief Parses one `ORDER_TRADE_UPDATE` message's `"o"` object into
    a domain `Order` — the exchange's own account of this order's current
    state, always trusted over whatever this app last believed
    (`EPIC-021H` §2.4).
    @raise KeyError A required field (`"c"`/`"s"`/`"S"`/`"o"`/`"q"`/`"X"`)
    is missing — a genuinely malformed payload, not merely an
    unrecognized enum value (`order_enum_parsing.py` handles that case
    without raising, `BUG-091`)."""
    o = payload["o"]
    order_time_raw = o.get("T")
    return Order(
        client_order_id=ClientOrderId(o["c"]),
        symbol=o["s"],
        side=OrderSide[o["S"]],
        order_type=order_type_or_unknown(o["o"]),
        quantity=Decimal(str(o["q"])),
        status=order_status_or_unknown(o["X"]),
        price=_decimal_or_none(o.get("p")),
        stop_price=_decimal_or_none(o.get("sp")),
        time_in_force=time_in_force_or_none(o.get("f")),
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


def account_update_position_pnls(payload: dict[str, Any]) -> dict[str, Decimal]:
    """@brief `{symbol: unrealized_pnl}` for every position `"a"."P"`
    reports on *this* `ACCOUNT_UPDATE` — not a full snapshot of every
    currently-open position (`BUG-092`): Binance only includes the
    positions that changed as part of this specific event, the same fact
    `account_update_changed_symbols` already documents. A closed position
    reports here too, with `"up"` `"0"` (going flat always zeroes uPnL) —
    the caller does not need to special-case it.
    @details The caller (`FuturesUserDataStream`) is responsible for
    folding this into a running per-symbol total across events — this
    function only ever reports what one message said, on purpose (`Pure
    parsing, no network`, this module's own docstring).
    """
    return {
        position["s"]: Decimal(str(position.get("up", "0")))
        for position in payload.get("a", {}).get("P", [])
    }


def account_update_wallet_balance(payload: dict[str, Any]) -> Decimal | None:
    """@brief The `_QUOTE_ASSET` wallet balance from one `ACCOUNT_UPDATE`'s
    `"a"."B"` array, or `None` when the payload carries no entry for it
    (`EPIC-021M` §4: "không có 'B' -> không crash, không sinh mẫu rác")."""
    balances = payload.get("a", {}).get("B", [])
    balance = next((b for b in balances if b.get("a") == _QUOTE_ASSET), None)
    return None if balance is None else Decimal(str(balance["wb"]))


def account_update_captured_at(payload: dict[str, Any]) -> datetime:
    """@brief The stream's own event time (`"E"`, ms) — matching
    `parse_order_trade_update`'s use of the exchange's own timestamps over
    local wall-clock time."""
    return datetime.fromtimestamp(payload["E"] / 1000, tz=UTC)
