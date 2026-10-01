"""`EPIC-027K` — domain `Order` <-> Binance Spot REST payload. Pure logic,
no network — same reasoning as `futures_order_payload_mapper.py`: catching a
mapping mistake here is cheap, before a live call confirms it the expensive
way (a rejected/misrouted order).

@details Genuinely different wire shape from Futures, not merely a
different prefix: Spot's `create_order`/`create_test_order` reject
`positionSide` and `reduceOnly` outright — both are One-way/Hedge-mode
Futures concepts (`architecture-rule.md` §5, `futures_order_payload_mapper
.py`'s own docstring) that have no Spot equivalent, since a Spot account
holds a balance, never a leveraged position to reduce. This module never
emits either field.

Only `OrderType.MARKET`/`OrderType.LIMIT` are supported — the two this
task's own title names. `STOP_MARKET`/`TAKE_PROFIT_MARKET` are Futures-only
order types on this app's `OrderType` enum (Binance Spot has its own
`STOP_LOSS`/`TAKE_PROFIT` family instead, which nothing in this app
constructs yet); sending either to Spot is refused here, before the
network, with a named reason — the same `InvalidOrderForSubmissionError`
`futures_order_payload_mapper.py` already raises for "this app built an
order the venue cannot accept."
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.order_enum_parsing import (
    order_status_or_unknown,
    order_type_or_unknown,
    time_in_force_or_none,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.invalid_order_for_submission import (
    InvalidOrderForSubmissionError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)

#: The only two order types Binance Spot's `create_order` accepts that this
#: app's `OrderType` enum also has a member for.
_SUPPORTED_SPOT_ORDER_TYPES = frozenset(
    {OrderType.MARKET, OrderType.LIMIT, OrderType.STOP_LIMIT}
)
#: `EPIC-028O` — the order types that rest with a limit price and a time in
#: force.
_LIMIT_PRICED_TYPES = frozenset({OrderType.LIMIT, OrderType.STOP_LIMIT})
#: Spot's spelling of a member whose name is not Binance's: a stop-limit is
#: `STOP_LOSS_LIMIT` (`price` + `stopPrice`; a buy stop waits above the
#: market, a sell stop below it). Read both ways.
SPOT_ORDER_TYPE_NAMES: dict[str, OrderType] = {"STOP_LOSS_LIMIT": OrderType.STOP_LIMIT}
_SPOT_WIRE_TYPES = {member: name for name, member in SPOT_ORDER_TYPE_NAMES.items()}


def _require_step_aligned(quantity: Decimal, step_size: Decimal, label: str) -> None:
    if step_size > 0 and quantity % step_size != 0:
        raise InvalidOrderForSubmissionError(
            f"{label} {quantity} is not a multiple of step size {step_size} — "
            "round it with OrderQuantityRoundingPolicy before submitting."
        )


def map_order_to_spot_params(
    order: Order, metadata: SymbolOrderMetadata
) -> dict[str, Any]:
    """@brief Builds the `**params` dict `python-binance`'s
    `create_order`/`create_test_order` expects from `order`.
    @raise InvalidOrderForSubmissionError `order.order_type` is not
    `MARKET`/`LIMIT`/`STOP_LIMIT` (Spot has no `STOP_MARKET`/
    `TAKE_PROFIT_MARKET` equivalent on this app's enum); or `order`'s
    quantity/price/stop price is not already rounded to `metadata`'s
    filters; or a type-required field is missing; or a quote amount is set
    on anything but a market buy. Never `positionSide`/`reduceOnly` on the returned dict — Spot's
    API has no such fields.
    """
    if order.order_type not in _SUPPORTED_SPOT_ORDER_TYPES:
        raise InvalidOrderForSubmissionError(
            f"{order.order_type.name} is not a Spot order type — Spot "
            "supports MARKET, LIMIT and STOP_LIMIT only."
        )

    params: dict[str, Any] = {
        "symbol": order.symbol,
        "side": order.side.value,
        "type": _SPOT_WIRE_TYPES.get(order.order_type, order.order_type.name),
        "newClientOrderId": str(order.client_order_id),
    }

    if order.quote_quantity is not None:
        # `EPIC-028O` — a market buy sized by what it spends: Binance fills
        # as much as the quote amount buys, so `quantity` is not sent.
        if order.order_type is not OrderType.MARKET or order.side is not OrderSide.BUY:
            raise InvalidOrderForSubmissionError(
                "Only a MARKET BUY can be sized by quote amount."
            )
        params["quoteOrderQty"] = str(order.quote_quantity)
    else:
        _require_step_aligned(
            order.quantity, metadata.step_size_for(order.order_type), "quantity"
        )
        params["quantity"] = str(order.quantity)

    if order.order_type in _LIMIT_PRICED_TYPES:
        if order.price is None:
            raise InvalidOrderForSubmissionError(
                f"{order.order_type.name} order is missing price."
            )
        if order.time_in_force is None:
            raise InvalidOrderForSubmissionError(
                f"{order.order_type.name} order is missing time_in_force."
            )
        _require_step_aligned(order.price, metadata.tick_size, "price")
        params["price"] = str(order.price)
        params["timeInForce"] = order.time_in_force.value

    if order.order_type is OrderType.STOP_LIMIT:
        if order.stop_price is None:
            raise InvalidOrderForSubmissionError(
                "STOP_LIMIT order is missing stop_price."
            )
        _require_step_aligned(order.stop_price, metadata.tick_size, "stop_price")
        params["stopPrice"] = str(order.stop_price)

    return params


def _decimal_or_none(raw: Any) -> Decimal | None:
    if raw is None:
        return None
    value = Decimal(str(raw))
    return value if value != 0 else None


def _order_time_or_none(payload: dict[str, Any]) -> datetime | None:
    """Same "last change over creation, `None` over a fabricated `now`"
    reasoning as `futures_order_payload_mapper._order_time_or_none()` —
    Spot's `create_order`/`cancel_order` responses carry `transactTime`
    (creation), not `updateTime`; `get_open_orders`'s own entries carry
    `time`/`updateTime` like Futures does. Checked in that order so a
    freshly-placed order's own creation time is not silently overwritten
    by a later, unrelated `updateTime` field this payload does not have."""
    raw = (
        payload.get("transactTime") or payload.get("updateTime") or payload.get("time")
    )
    return datetime.fromtimestamp(raw / 1000, tz=UTC) if raw else None


def map_spot_order_payload_to_order(payload: dict[str, Any]) -> Order:
    """@brief The reverse direction: one order object from a Binance Spot
    REST response (`place`/`cancel`/`get_open_orders`) back into a domain
    `Order`.
    @details No `reduceOnly`/`positionSide` fields exist on a Spot payload
    at all — `Order`'s own defaults apply. `stopPrice` exists on a
    stop-limit (`EPIC-028O`) and is `"0.00000000"` on every other type,
    read as `None`.
    @raise KeyError A required field is missing — a genuinely malformed
    payload (`futures_order_payload_mapper.map_futures_order_payload_to_order`'s
    own docstring gives the same reasoning: an unrecognized `type`/`status`
    value degrades to `UNKNOWN` without raising, but a missing field does
    not).
    """
    return Order(
        client_order_id=ClientOrderId(payload["clientOrderId"]),
        symbol=payload["symbol"],
        side=OrderSide[payload["side"]],
        order_type=order_type_or_unknown(payload["type"], SPOT_ORDER_TYPE_NAMES),
        quantity=Decimal(str(payload["origQty"])),
        status=order_status_or_unknown(payload["status"]),
        price=_decimal_or_none(payload.get("price")),
        stop_price=_decimal_or_none(payload.get("stopPrice")),
        time_in_force=time_in_force_or_none(payload.get("timeInForce")),
        order_time=_order_time_or_none(payload),
    )
