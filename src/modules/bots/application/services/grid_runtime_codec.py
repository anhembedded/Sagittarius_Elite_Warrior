"""`EPIC-029E` — a Grid's runtime as the store keeps it (ADR D4).

`StoredBot.runtime` is opaque JSON to everything but the kind that wrote it.
This is the Grid's reading and writing of it. Money is written as strings, so
no float ever touches a price or a quantity on the way to disk and back. A
runtime that does not parse raises `GridRuntimeCodecError` naming the field:
the executor then refuses to act on the bot rather than guess its ladder.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import JsonValue
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_level_fsm_matrix import (
    LevelState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    GridRuntime,
    HeldOrder,
    LevelOrder,
    RuntimeLevel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide


class GridRuntimeCodecError(ValueError):
    """A stored Grid runtime that cannot be read; names the field."""


def encode_runtime(runtime: GridRuntime) -> dict[str, JsonValue]:
    return {
        "levels": [_encode_level(level) for level in runtime.levels],
        "inventory": str(runtime.inventory),
        "cost": str(runtime.cost),
        "realised_profit": str(runtime.realised_profit),
        "completed_cycles": runtime.completed_cycles,
        "held": [_encode_held(held) for held in runtime.held],
        "reason": runtime.reason.value if runtime.reason else None,
        "reason_detail": runtime.reason_detail,
    }


def decode_runtime(data: Mapping[str, JsonValue]) -> GridRuntime:
    """@raise GridRuntimeCodecError A field is missing or malformed."""
    reason = data.get("reason")
    return GridRuntime(
        levels=tuple(
            _decode_level(_mapping(item, "level")) for item in _list(data, "levels")
        ),
        inventory=_decimal(data, "inventory"),
        cost=_decimal(data, "cost"),
        realised_profit=_decimal(data, "realised_profit"),
        completed_cycles=_int(data, "completed_cycles"),
        held=tuple(
            _decode_held(_mapping(item, "held")) for item in _list(data, "held")
        ),
        reason=_enum(GridReason, reason, "reason") if reason is not None else None,
        reason_detail=_text(data, "reason_detail"),
    )


def _encode_level(level: RuntimeLevel) -> dict[str, JsonValue]:
    return {
        "index": level.index,
        "price": str(level.price),
        "buy_quantity": str(level.buy_quantity),
        "state": level.state.value,
        "order": _encode_order(level.order) if level.order else None,
        "ended_at": [moment.isoformat() for moment in level.ended_at],
    }


def _encode_order(order: LevelOrder) -> dict[str, JsonValue]:
    return {
        "client_order_id": order.client_order_id,
        "side": order.side.value,
        "price": str(order.price),
        "quantity": str(order.quantity),
        "executed": str(order.executed),
        "base_fee": str(order.base_fee),
        "quote_fee": str(order.quote_fee),
        "carried_executed": str(order.carried_executed),
        "carried_base_fee": str(order.carried_base_fee),
        "paired_buy_price": _optional(order.paired_buy_price),
        "paired_buy_fee_quote": str(order.paired_buy_fee_quote),
    }


def _encode_held(held: HeldOrder) -> dict[str, JsonValue]:
    return {
        "level_index": held.level_index,
        "side": held.side.value,
        "quantity": str(held.quantity),
        "paired_buy_price": _optional(held.paired_buy_price),
        "paired_buy_fee_quote": str(held.paired_buy_fee_quote),
        "carried_executed": str(held.carried_executed),
        "carried_base_fee": str(held.carried_base_fee),
    }


def _decode_level(data: Mapping[str, JsonValue]) -> RuntimeLevel:
    order = data.get("order")
    return RuntimeLevel(
        index=_int(data, "index"),
        price=_decimal(data, "price"),
        buy_quantity=_decimal(data, "buy_quantity"),
        state=_enum(LevelState, data.get("state"), "state"),
        order=_decode_order(_mapping(order, "order")) if order is not None else None,
        ended_at=tuple(_moment(item) for item in _list(data, "ended_at")),
    )


def _decode_order(data: Mapping[str, JsonValue]) -> LevelOrder:
    return LevelOrder(
        client_order_id=_text(data, "client_order_id"),
        side=_enum(OrderSide, data.get("side"), "side"),
        price=_decimal(data, "price"),
        quantity=_decimal(data, "quantity"),
        executed=_decimal(data, "executed"),
        base_fee=_decimal(data, "base_fee"),
        quote_fee=_decimal(data, "quote_fee"),
        carried_executed=_decimal(data, "carried_executed"),
        carried_base_fee=_decimal(data, "carried_base_fee"),
        paired_buy_price=_optional_decimal(data, "paired_buy_price"),
        paired_buy_fee_quote=_decimal(data, "paired_buy_fee_quote"),
    )


def _decode_held(data: Mapping[str, JsonValue]) -> HeldOrder:
    return HeldOrder(
        level_index=_int(data, "level_index"),
        side=_enum(OrderSide, data.get("side"), "side"),
        quantity=_decimal(data, "quantity"),
        paired_buy_price=_optional_decimal(data, "paired_buy_price"),
        paired_buy_fee_quote=_decimal(data, "paired_buy_fee_quote"),
        carried_executed=_decimal(data, "carried_executed"),
        carried_base_fee=_decimal(data, "carried_base_fee"),
    )


def _optional(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _mapping(value: JsonValue, field: str) -> Mapping[str, JsonValue]:
    if not isinstance(value, dict):
        raise GridRuntimeCodecError(f"{field} is not an object")
    return value


def _list(data: Mapping[str, JsonValue], field: str) -> list[JsonValue]:
    value = data.get(field)
    if not isinstance(value, list):
        raise GridRuntimeCodecError(f"{field} is not a list")
    return value


def _text(data: Mapping[str, JsonValue], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str):
        raise GridRuntimeCodecError(f"{field} is not text")
    return value


def _int(data: Mapping[str, JsonValue], field: str) -> int:
    value = data.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise GridRuntimeCodecError(f"{field} is not a whole number")
    return value


def _decimal(data: Mapping[str, JsonValue], field: str) -> Decimal:
    text = _text(data, field)
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise GridRuntimeCodecError(f"{field} is not a number: {text!r}") from None
    if not value.is_finite():
        raise GridRuntimeCodecError(f"{field} is not a finite number: {text!r}")
    return value


def _optional_decimal(data: Mapping[str, JsonValue], field: str) -> Decimal | None:
    return None if data.get(field) is None else _decimal(data, field)


def _moment(value: JsonValue) -> datetime:
    if not isinstance(value, str):
        raise GridRuntimeCodecError("ended_at holds a value that is not text")
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        raise GridRuntimeCodecError(f"ended_at is not a moment: {value!r}") from None
    if moment.tzinfo is None:
        raise GridRuntimeCodecError(f"ended_at is not timezone-aware: {value!r}")
    return moment


def _enum[E: (LevelState, OrderSide, GridReason)](
    kind: type[E], value: JsonValue, field: str
) -> E:
    try:
        return kind(value)
    except ValueError:
        raise GridRuntimeCodecError(
            f"{field} is not one of {kind.__name__}: {value!r}"
        ) from None
