"""`EPIC-021F` — domain `Order`/`LivePosition` ↔ Binance Futures REST
payload. Pure logic, no network — this is what makes it the cheapest place
to catch a mapping mistake, before a live call ever confirms it the
expensive way (a rejected/misrouted order).

@details `side` (BUY/SELL) and `positionSide` are two different fields on
Binance's own API; this app always sends `positionSide=BOTH` (One-way,
already enforced at the connection-check door by `EPIC-021D`'s
`ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED`). `timeInForce` is only
valid for `LIMIT`. `quantity`/`price`/`stop_price` are trusted to already
be rounded to the symbol's `stepSize`/`tickSize`
(`OrderQuantityRoundingPolicy`, `EPIC-021C`) — this module never rounds
anything itself; it rejects an unrounded `Order` with a named error
instead, so domain and exchange can never silently disagree about the
quantity that was actually sent.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.entities.futures_symbol_metadata import (
    FuturesSymbolMetadata,
)
from Sagittarius_Elite_Warrior.src.domain.trading.client_order_id import ClientOrderId
from Sagittarius_Elite_Warrior.src.domain.trading.live_position import (
    LiquidationPrice,
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.domain.trading.order import Order
from Sagittarius_Elite_Warrior.src.domain.trading.order_status import OrderStatus
from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
from Sagittarius_Elite_Warrior.src.domain.trading.time_in_force import TimeInForce
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide

#: `positionSide` Binance's API expects when the account is One-way mode —
#: never anything else in this epic (ADR §6, `EPIC-021D`).
_ONE_WAY_POSITION_SIDE = "BOTH"

_STOP_ORDER_TYPES = frozenset({OrderType.STOP_MARKET, OrderType.TAKE_PROFIT_MARKET})


class InvalidOrderForSubmissionError(ValueError):
    """@brief Raised instead of silently rounding when `Order` does not
    already align to the symbol's `stepSize`/`tickSize`, or is missing a
    field its `order_type` requires.
    @details Never fixed up here — see this module's own docstring for
    why. The caller (`FuturesTradingClient`) is expected to have built the
    order through `OrderQuantityRoundingPolicy` in the first place; this
    is the safety net for the day something upstream forgets to.
    """


def _require_step_aligned(quantity: Decimal, step_size: Decimal, label: str) -> None:
    if step_size > 0 and quantity % step_size != 0:
        raise InvalidOrderForSubmissionError(
            f"{label} {quantity} is not a multiple of step size {step_size} — "
            "round it with OrderQuantityRoundingPolicy before submitting."
        )


def map_order_to_futures_params(
    order: Order, metadata: FuturesSymbolMetadata
) -> dict[str, Any]:
    """@brief Builds the `**params` dict `python-binance`'s
    `futures_create_order`/`futures_create_test_order` expects from `order`.
    @raise InvalidOrderForSubmissionError If `order`'s quantity/price/stop
    price is not already rounded to `metadata`'s filters, or a
    type-required field (`price`+`time_in_force` for `LIMIT`, `stop_price`
    for the stop types) is missing.
    """
    _require_step_aligned(order.quantity, metadata.step_size, "quantity")

    params: dict[str, Any] = {
        "symbol": order.symbol,
        "side": order.side.value,
        "type": order.order_type.name,
        "quantity": str(order.quantity),
        "newClientOrderId": str(order.client_order_id),
        "positionSide": _ONE_WAY_POSITION_SIDE,
        "reduceOnly": order.reduce_only,
    }

    if order.order_type is OrderType.LIMIT:
        if order.price is None:
            raise InvalidOrderForSubmissionError("LIMIT order is missing price.")
        if order.time_in_force is None:
            raise InvalidOrderForSubmissionError(
                "LIMIT order is missing time_in_force."
            )
        _require_step_aligned(order.price, metadata.tick_size, "price")
        params["price"] = str(order.price)
        params["timeInForce"] = order.time_in_force.value

    if order.order_type in _STOP_ORDER_TYPES:
        if order.stop_price is None:
            raise InvalidOrderForSubmissionError(
                f"{order.order_type.name} order is missing stop_price."
            )
        _require_step_aligned(order.stop_price, metadata.tick_size, "stop_price")
        params["stopPrice"] = str(order.stop_price)

    return params


def _decimal_or_none(raw: Any) -> Decimal | None:
    if raw is None:
        return None
    value = Decimal(str(raw))
    return value if value != 0 else None


def map_futures_order_payload_to_order(payload: dict[str, Any]) -> Order:
    """@brief The reverse direction: one order object from a Binance
    Futures REST response (`place`/`cancel`/`get_open_orders`) back into a
    domain `Order`.
    @details `price`/`stop_price` come back as `"0"`/`"0.0"` from Binance
    for order types that don't use them, not as an absent field — treated
    as `None` here, matching how `Order` itself represents "not
    applicable" rather than "zero".
    """
    order_type = OrderType[payload["type"]]
    time_in_force_raw = payload.get("timeInForce")
    return Order(
        client_order_id=ClientOrderId(payload["clientOrderId"]),
        symbol=payload["symbol"],
        side=OrderSide[payload["side"]],
        order_type=order_type,
        quantity=Decimal(str(payload["origQty"])),
        status=OrderStatus[payload["status"]],
        price=_decimal_or_none(payload.get("price")),
        stop_price=_decimal_or_none(payload.get("stopPrice")),
        time_in_force=(TimeInForce(time_in_force_raw) if time_in_force_raw else None),
        reduce_only=bool(payload.get("reduceOnly", False)),
    )


def map_futures_position_payload_to_live_position(
    payload: dict[str, Any],
) -> LivePosition:
    """@brief One entry of `futures_position_information()`'s response into
    a domain `LivePosition`.
    @details `updateTime` is not present on every version of this endpoint
    this app has seen documented; falls back to "now" rather than
    fabricating a stale timestamp when it's missing.
    """
    liquidation_price_raw = _decimal_or_none(payload.get("liquidationPrice"))
    update_time_ms = payload.get("updateTime")
    updated_at = (
        datetime.fromtimestamp(update_time_ms / 1000, tz=UTC)
        if update_time_ms
        else datetime.now(UTC)
    )
    return LivePosition(
        symbol=payload["symbol"],
        position_amt=Decimal(str(payload["positionAmt"])),
        entry_price=Decimal(str(payload["entryPrice"])),
        mark_price=Decimal(str(payload["markPrice"])),
        unrealized_pnl=Decimal(str(payload["unRealizedProfit"])),
        leverage=int(payload["leverage"]),
        margin_type=(
            MarginType.ISOLATED
            if str(payload.get("marginType", "")).lower() == "isolated"
            else MarginType.CROSSED
        ),
        liquidation_price=(
            LiquidationPrice(liquidation_price_raw)
            if liquidation_price_raw is not None
            else None
        ),
        updated_at=updated_at,
    )
