"""`EPIC-047A` — what a type hint means on the wire, read once for the codec and the schema.

The codec and the handshake's schema must agree on what a hint is; both read it here, so a
type the codec cannot carry cannot enter the hash either.
"""

from __future__ import annotations

import dataclasses
import functools
import operator
import types
import typing
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from functools import cache

from Sagittarius_Elite_Warrior.src.core.contracts.wire_name import wire_name_of
from Sagittarius_Elite_Warrior.src.support.wire.wire_errors import WireSchemaError

_ITEMS_ARITY = 2  # `tuple[X, ...]` is the item and an Ellipsis
SCALARS: dict[type, str] = {
    str: "text",
    int: "integer",
    bool: "boolean",
    Decimal: "decimal",
    datetime: "datetime",
    timedelta: "duration",
}


@dataclass(frozen=True, slots=True)
class ScalarShape:
    py: type
    kind: str


@dataclass(frozen=True, slots=True)
class EnumShape:
    cls: type[Enum]


@dataclass(frozen=True, slots=True)
class RecordShape:
    cls: type
    fields: tuple[tuple[str, object], ...]


@dataclass(frozen=True, slots=True)
class OptionalShape:
    inner: object


@dataclass(frozen=True, slots=True)
class ItemsShape:
    """`tuple[X, ...]`: any number of one item type."""

    item: object


@dataclass(frozen=True, slots=True)
class FixedTupleShape:
    items: tuple[object, ...]


@dataclass(frozen=True, slots=True)
class MappingShape:
    value: object


@dataclass(frozen=True, slots=True)
class UnionShape:
    """Records told apart by their wire names."""

    members: tuple[tuple[str, type], ...]


type Shape = (
    ScalarShape
    | EnumShape
    | RecordShape
    | OptionalShape
    | ItemsShape
    | FixedTupleShape
    | MappingShape
    | UnionShape
)


@cache
def _field_hints(cls: type) -> tuple[tuple[str, object], ...]:
    hints = typing.get_type_hints(cls)
    return tuple((f.name, hints[f.name]) for f in dataclasses.fields(cls))


def _unwrap(hint: object) -> object:
    while True:
        if isinstance(hint, typing.TypeAliasType):
            hint = hint.__value__
        elif hasattr(hint, "__supertype__"):
            hint = hint.__supertype__
        else:
            return hint


def shape_of(hint: object) -> Shape:
    """The wire meaning of a hint, or a `WireSchemaError` saying why it has none."""
    hint = _unwrap(hint)
    origin = typing.get_origin(hint)
    if origin in (typing.Union, types.UnionType):
        return _union_shape(typing.get_args(hint))
    if origin is tuple:
        args = typing.get_args(hint)
        if len(args) == _ITEMS_ARITY and args[1] is Ellipsis:
            return ItemsShape(args[0])
        return FixedTupleShape(args)
    if origin is not None and getattr(origin, "__name__", "") == "Mapping":
        key, value = typing.get_args(hint)
        if key is not str:
            raise WireSchemaError(
                f"a mapping crosses the wire with text keys, not {key!r}"
            )
        return MappingShape(value)
    if origin is not None:
        raise WireSchemaError(f"{hint!r} has no wire form")
    if isinstance(hint, type):
        return _class_shape(hint)
    raise WireSchemaError(f"{hint!r} has no wire form")


def _class_shape(cls: type) -> Shape:
    kind = SCALARS.get(cls)
    if kind is not None:
        return ScalarShape(cls, kind)
    if issubclass(cls, Enum):
        return EnumShape(cls)
    if dataclasses.is_dataclass(cls):
        return RecordShape(cls, _field_hints(cls))
    if cls is float:
        raise WireSchemaError(
            "float has no wire form: a price or an amount is a Decimal, text on the wire"
        )
    raise WireSchemaError(f"{cls.__qualname__} has no wire form")


def _flatten(args: tuple[object, ...]) -> list[object]:
    """The members of a union, the unions behind aliases opened and a repeated member once."""
    members: list[object] = []
    for arg in args:
        arg = _unwrap(arg)
        if typing.get_origin(arg) in (typing.Union, types.UnionType):
            inner = _flatten(typing.get_args(arg))
        else:
            inner = [arg]
        members.extend(m for m in inner if m not in members)
    return members


def _union_shape(args: tuple[object, ...]) -> Shape:
    members = _flatten(args)
    if type(None) in members:
        rest = [m for m in members if m is not type(None)]
        return OptionalShape(functools.reduce(operator.or_, rest))
    named: list[tuple[str, type]] = []
    for member in members:
        if not (isinstance(member, type) and dataclasses.is_dataclass(member)):
            raise WireSchemaError(
                f"a union carries records told apart by wire names; {member!r} is not a record"
            )
        name = wire_name_of(member)
        if name is None:
            raise WireSchemaError(
                f"{member.__qualname__} is a member of a union and has no wire name: "
                "add @wire_name('sew.…/1') to it"
            )
        named.append((name, member))
    if len({n for n, _ in named}) != len(named):
        raise WireSchemaError("two members of one union share a wire name")
    return UnionShape(tuple(named))
