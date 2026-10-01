"""`EPIC-028R` — domain `Order` ↔ Binance USD-M Algo Order API payloads.

@details Since 2025-12-09 Binance serves every USD-M conditional order
(`STOP`, `STOP_MARKET`, `TAKE_PROFIT`, `TAKE_PROFIT_MARKET`,
`TRAILING_STOP_MARKET`) through the Algo Order API: `POST /fapi/v1/algoOrder`,
listed by `GET /fapi/v1/openAlgoOrders` and `allAlgoOrders`, cancelled by
`DELETE /fapi/v1/algoOrder` and `algoOpenOrders`. An algo order is
identified by its `clientAlgoId`, which this app sets to its own client order
id, so an algo order is tracked exactly like a regular one.

Field names follow Binance's USD-M documentation of the Algo Order API and
`python-binance` 1.0.37's `client.py` (paths and parameters); no live call
verified them, because egress to `*.binance.*` is blocked in this sandbox.
The same disclosure as `futures_account_reader.py`.

Plausible extensions, each one entry in a table here:
- `STOP_MARKET` / `TAKE_PROFIT_MARKET` sent (028I's TP/SL): one entry in
  `_ALGO_TYPE_NAMES` plus their params (no limit price);
- a trailing stop: a new `OrderType` member and its `callbackRate`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.order_enum_parsing import (
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)

#: The only `algoType` Binance's USD-M Algo Order API serves.
ALGO_TYPE_CONDITIONAL = "CONDITIONAL"
#: What the trigger compares against: the last traded price, the same price
#: the app's own stop check (`check_stop_trigger_side`) judges a stop by.
_WORKING_TYPE_LAST_PRICE = "CONTRACT_PRICE"
_ONE_WAY_POSITION_SIDE = "BOTH"

#: The app's order types sent through the Algo Order API, with their USD-M
#: name. A stop-limit is `STOP`.
_ALGO_TYPE_NAMES: dict[OrderType, str] = {OrderType.STOP_LIMIT: "STOP"}
#: The read direction: Binance's conditional type names this app's enum
#: spells differently. `TAKE_PROFIT` (a take-profit limit) has no member and
#: reads as `OrderType.UNKNOWN`, the `BUG-091` idiom.
_ALGO_TYPE_READ_NAMES: dict[str, OrderType] = {"STOP": OrderType.STOP_LIMIT}

#: `algoStatus` → `OrderStatus`. `TRIGGERING` is still waiting for its
#: regular order to be placed, so it is open; `TRIGGERED` and `FINISHED` have
#: placed it, so the conditional order itself is over.
_ALGO_STATUSES: dict[str, OrderStatus] = {
    "NEW": OrderStatus.NEW,
    "TRIGGERING": OrderStatus.NEW,
    "TRIGGERED": OrderStatus.TRIGGERED,
    "FINISHED": OrderStatus.TRIGGERED,
    "CANCELED": OrderStatus.CANCELED,
    "REJECTED": OrderStatus.REJECTED,
    "EXPIRED": OrderStatus.EXPIRED,
}


def order_status_from_algo(raw: str) -> OrderStatus:
    """@return `raw` (an `algoStatus`) as an `OrderStatus`; `UNKNOWN` for a
    status this app has no name for (`BUG-091`)."""
    return _ALGO_STATUSES.get(raw, OrderStatus.UNKNOWN)


def order_type_from_algo(raw: str) -> OrderType:
    """@return `raw` (an algo `orderType`) as an `OrderType`."""
    return order_type_or_unknown(raw, _ALGO_TYPE_READ_NAMES)


def is_algo_routed(order_type: OrderType) -> bool:
    """Whether the Futures client sends this type through the Algo Order
    API rather than `POST /fapi/v1/order`."""
    return order_type in _ALGO_TYPE_NAMES


def map_order_to_futures_algo_params(
    order: Order, metadata: SymbolOrderMetadata
) -> dict[str, Any]:
    """@brief The `**params` for `futures_create_algo_order` from `order`.
    @raise InvalidOrderForSubmissionError `order` is not an algo-routed type,
    lacks its stop, limit price or time in force, or is not rounded to the
    symbol's filters."""
    type_name = _ALGO_TYPE_NAMES.get(order.order_type)
    if type_name is None:
        raise InvalidOrderForSubmissionError(
            f"{order.order_type.name} is not sent through the Algo Order API."
        )
    if order.stop_price is None or order.price is None:
        raise InvalidOrderForSubmissionError(
            "A stop-limit needs its stop price and its limit price."
        )
    if order.time_in_force is None:
        raise InvalidOrderForSubmissionError("A stop-limit needs a time in force.")
    _require_multiple(order.quantity, metadata.step_size, "quantity")
    _require_multiple(order.price, metadata.tick_size, "price")
    _require_multiple(order.stop_price, metadata.tick_size, "stop price")
    return {
        "algoType": ALGO_TYPE_CONDITIONAL,
        "symbol": order.symbol,
        "side": order.side.value,
        "positionSide": _ONE_WAY_POSITION_SIDE,
        "type": type_name,
        "quantity": str(order.quantity),
        "price": str(order.price),
        "triggerPrice": str(order.stop_price),
        "timeInForce": order.time_in_force.value,
        "workingType": _WORKING_TYPE_LAST_PRICE,
        "reduceOnly": order.reduce_only,
        "clientAlgoId": str(order.client_order_id),
    }


def map_futures_algo_payload_to_order(payload: dict[str, Any]) -> Order:
    """@brief One algo order (`algoOrder`, `openAlgoOrders`, `allAlgoOrders`)
    as a domain `Order`, identified by its `clientAlgoId`.
    @raise KeyError A required field is missing; an unrecognized type or
    status reads as `UNKNOWN` instead (`BUG-091`)."""
    return Order(
        client_order_id=ClientOrderId(payload["clientAlgoId"]),
        symbol=payload["symbol"],
        side=OrderSide[payload["side"]],
        order_type=order_type_from_algo(payload["orderType"]),
        quantity=Decimal(str(payload["quantity"])),
        status=order_status_from_algo(payload["algoStatus"]),
        price=_decimal_or_none(payload.get("price")),
        stop_price=_decimal_or_none(payload.get("triggerPrice")),
        time_in_force=time_in_force_or_none(payload.get("timeInForce")),
        reduce_only=bool(payload.get("reduceOnly", False)),
        order_time=_time_or_none(
            payload.get("updateTime") or payload.get("createTime")
        ),
    )


def map_futures_algo_history_order(payload: dict[str, Any]) -> OrderRecord:
    """@brief One `allAlgoOrders` row. Its executed quantity is zero by
    construction: the fill belongs to the regular order a triggered algo
    order placed, which `allOrders` lists, so nothing is counted twice.
    @raise KeyError A required field is missing."""
    created = _time_or_none(payload["createTime"])
    if created is None:
        raise KeyError("createTime")
    return OrderRecord(
        order=map_futures_algo_payload_to_order(payload),
        executed_quantity=Decimal(0),
        average_price=None,
        created_at=created,
    )


def _require_multiple(value: Decimal, step: Decimal, label: str) -> None:
    if step > 0 and value % step != 0:
        raise InvalidOrderForSubmissionError(
            f"{label} {value} is not a multiple of {step} — round it with "
            "OrderQuantityRoundingPolicy before submitting."
        )


def _decimal_or_none(raw: Any) -> Decimal | None:
    if raw is None or raw == "":
        return None
    value = Decimal(str(raw))
    return value if value != 0 else None


def _time_or_none(raw_ms: Any) -> datetime | None:
    return datetime.fromtimestamp(int(raw_ms) / 1000, tz=UTC) if raw_ms else None
