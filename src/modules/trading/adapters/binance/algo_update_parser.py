"""`EPIC-028R` — the Futures user-data stream's `ALGO_UPDATE` event: one
conditional order's state, and once triggered, the regular order it placed.

@details Binance's documented shape (USD-M "Algo Order Update"), under `"o"`:
`caid` the client algo id (the app's own client order id), `s` symbol, `S`
side, `o` order type, `q` quantity, `X` algo status, `p` limit price, `tp`
trigger price, `f` time in force, `R` reduce-only, and `ai` the id of the
regular order a triggered algo order placed (empty until then). Field names
come from Binance's documentation; no live stream verified them (egress to
`*.binance.*` is blocked here), the same disclosure as the REST mapper.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_algo_order_mapper import (
    order_status_from_algo,
    order_type_from_algo,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.order_enum_parsing import (
    time_in_force_or_none,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide

#: The `"e"` (event type) of an algo order's update.
ALGO_UPDATE = "ALGO_UPDATE"


@dataclass(frozen=True)
class AlgoUpdate:
    """One `ALGO_UPDATE`: the conditional order, and the id of the regular
    order it placed once triggered."""

    order: Order
    #: `ai` — `None` until the algo order has triggered.
    placed_order_id: int | None


def parse_algo_update(payload: dict[str, Any]) -> AlgoUpdate:
    """@raise KeyError A required field (`caid`, `s`, `S`, `o`, `q`, `X`) is
    missing; an unrecognized type or status reads as `UNKNOWN` (`BUG-091`).
    @raise ValueError `ai` is present but not an order id."""
    o = payload["o"]
    event_time = payload.get("T") or payload.get("E")
    order = Order(
        client_order_id=ClientOrderId(o["caid"]),
        symbol=o["s"],
        side=OrderSide[o["S"]],
        order_type=order_type_from_algo(o["o"]),
        quantity=Decimal(str(o["q"])),
        status=order_status_from_algo(o["X"]),
        price=_decimal_or_none(o.get("p")),
        stop_price=_decimal_or_none(o.get("tp")),
        time_in_force=time_in_force_or_none(o.get("f")),
        reduce_only=bool(o.get("R", False)),
        order_time=(
            datetime.fromtimestamp(event_time / 1000, tz=UTC) if event_time else None
        ),
    )
    placed = o.get("ai")
    return AlgoUpdate(order, int(placed) if placed not in (None, "", 0) else None)


def order_trade_update_order_id(payload: dict[str, Any]) -> int | None:
    """@return The exchange's id (`"o"."i"`) of the order one
    `ORDER_TRADE_UPDATE` reports, or `None` when the message carries none."""
    raw = payload["o"].get("i")
    return int(raw) if raw not in (None, "") else None


def _decimal_or_none(raw: Any) -> Decimal | None:
    if raw is None or raw == "":
        return None
    value = Decimal(str(raw))
    return value if value != 0 else None
