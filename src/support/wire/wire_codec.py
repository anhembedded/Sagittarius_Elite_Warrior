"""`EPIC-047A` — one reflective codec: a contract value to JSON-ready data and back, from its type hints.

A record is a JSON object with one key per dataclass field; a tagged union adds `"$type"`, the
member's wire name; an optional is `null`; a tuple is an array. Money is text: a `Decimal`
keeps every digit it was given (`12.3400`, `1E-8`) and never passes through a float. A
datetime keeps its offset (a naive one stays naive). A duration is whole microseconds.

It refuses rather than guesses. A message with a missing field, an extra field, an unknown
wire name or a wrong type is a `WireDecodeError`; no field is ever filled from its default.
A type with no wire form (a float, a union member without a name) is a `WireSchemaError`.
The codec holds no type list: which types may cross is the closed list of `WireRoots`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import Enum
from types import MappingProxyType
from typing import Any

from Sagittarius_Elite_Warrior.src.support.wire.wire_errors import (
    WireDecodeError,
    WireSchemaError,
)
from Sagittarius_Elite_Warrior.src.support.wire.wire_shape import (
    EnumShape,
    FixedTupleShape,
    ItemsShape,
    MappingShape,
    OptionalShape,
    RecordShape,
    ScalarShape,
    Shape,
    UnionShape,
    shape_of,
)

type JsonData = object
TYPE_KEY = "$type"
_MICROSECOND = timedelta(microseconds=1)


def encode(value: object, hint: object) -> JsonData:
    """The wire form of `value`, which must be what `hint` says."""
    return _encode(value, shape_of(hint), hint_name=_name(hint))


def decode(doc: JsonData, hint: object) -> object:
    """The value a wire form stands for, or a `WireDecodeError` saying where it is wrong."""
    return _decode(doc, shape_of(hint), _name(hint))


def _name(hint: object) -> str:
    return getattr(hint, "__name__", None) or str(hint)


def _encode(value: object, shape: Shape, hint_name: str) -> JsonData:
    return _ENCODERS[type(shape)](value, shape, hint_name)


def _encode_enum(value: object, shape: EnumShape, hint_name: str) -> JsonData:
    if type(value) is not shape.cls:
        raise _wrong_class(value, shape.cls.__name__)
    return value.value  # type: ignore[attr-defined]


def _encode_record(value: object, shape: RecordShape, hint_name: str) -> JsonData:
    if type(value) is not shape.cls:
        raise _wrong_class(value, shape.cls.__qualname__)
    return {n: _encode(getattr(value, n), shape_of(h), n) for n, h in shape.fields}


def _encode_optional(value: object, shape: OptionalShape, hint_name: str) -> JsonData:
    return None if value is None else _encode(value, shape_of(shape.inner), hint_name)


def _encode_items(value: object, shape: ItemsShape, hint_name: str) -> JsonData:
    return [_encode(v, shape_of(shape.item), hint_name) for v in _sequence(value)]


def _encode_fixed(value: object, shape: FixedTupleShape, hint_name: str) -> JsonData:
    pairs = zip(_sequence(value), shape.items, strict=True)
    return [_encode(v, shape_of(h), hint_name) for v, h in pairs]


def _encode_mapping(value: object, shape: MappingShape, hint_name: str) -> JsonData:
    inner = shape_of(shape.value)
    return {
        _text_key(k): _encode(v, inner, hint_name) for k, v in _mapping(value).items()
    }


def _encode_union(value: object, shape: UnionShape, hint_name: str) -> JsonData:
    for name, cls in shape.members:
        if type(value) is cls:
            return {TYPE_KEY: name, **_encode(value, shape_of(cls), name)}  # type: ignore[dict-item]
    raise _wrong_class(value, " | ".join(c.__qualname__ for _, c in shape.members))


def _encode_scalar(value: object, shape: ScalarShape, hint_name: str) -> JsonData:
    if type(value) is not shape.py:
        raise _wrong_class(value, shape.py.__name__)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise WireSchemaError(
                f"{hint_name}: a Decimal crosses the wire only if finite, not {value}"
            )
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, timedelta):
        return value // _MICROSECOND
    return value


_ENCODERS: dict[type, Callable[[Any, Any, str], JsonData]] = {
    ScalarShape: _encode_scalar,
    EnumShape: _encode_enum,
    RecordShape: _encode_record,
    OptionalShape: _encode_optional,
    ItemsShape: _encode_items,
    FixedTupleShape: _encode_fixed,
    MappingShape: _encode_mapping,
    UnionShape: _encode_union,
}


def _decode(doc: JsonData, shape: Shape, path: str) -> object:
    return _DECODERS[type(shape)](doc, shape, path)


def _decode_optional(doc: JsonData, shape: OptionalShape, path: str) -> object:
    return None if doc is None else _decode(doc, shape_of(shape.inner), path)


def _decode_items(doc: JsonData, shape: ItemsShape, path: str) -> object:
    inner = shape_of(shape.item)
    return tuple(
        _decode(d, inner, f"{path}[{i}]") for i, d in enumerate(_array(doc, path))
    )


def _decode_mapping(doc: JsonData, shape: MappingShape, path: str) -> object:
    inner = shape_of(shape.value)
    return MappingProxyType(
        {k: _decode(v, inner, f"{path}.{k}") for k, v in _object(doc, path).items()}
    )


def _decode_scalar(doc: JsonData, shape: ScalarShape, path: str) -> object:
    parse = _SCALAR_PARSERS.get(shape.py)
    if parse is not None:
        return parse(doc, path)
    if type(doc) is not shape.py:
        raise WireDecodeError(f"{path}: expected {shape.kind}, got {_describe(doc)}")
    return doc


def _decode_decimal(doc: JsonData, path: str) -> Decimal:
    if type(doc) is not str:
        raise WireDecodeError(f"{path}: expected decimal as text, got {_describe(doc)}")
    try:
        value = Decimal(doc)
    except InvalidOperation:
        raise WireDecodeError(f"{path}: {doc!r} is not a decimal") from None
    if not value.is_finite():
        raise WireDecodeError(f"{path}: {doc!r} is not a finite decimal")
    return value


def _decode_datetime(doc: JsonData, path: str) -> datetime:
    if type(doc) is not str:
        raise WireDecodeError(
            f"{path}: expected datetime as text, got {_describe(doc)}"
        )
    try:
        return datetime.fromisoformat(doc)
    except ValueError:
        raise WireDecodeError(f"{path}: {doc!r} is not an ISO datetime") from None


def _decode_duration(doc: JsonData, path: str) -> timedelta:
    if type(doc) is not int:
        raise WireDecodeError(
            f"{path}: expected duration as whole microseconds, got {_describe(doc)}"
        )
    try:
        return timedelta(microseconds=doc)
    except OverflowError:
        raise WireDecodeError(f"{path}: {doc} microseconds is out of range") from None


_SCALAR_PARSERS: dict[type, Callable[[JsonData, str], object]] = {
    Decimal: _decode_decimal,
    datetime: _decode_datetime,
    timedelta: _decode_duration,
}


def _decode_enum(doc: JsonData, shape: EnumShape, path: str) -> Enum:
    cls = shape.cls
    try:
        return cls(doc)
    except ValueError:
        raise WireDecodeError(
            f"{path}: {doc!r} is not a {cls.__name__} ({', '.join(repr(m.value) for m in cls)})"
        ) from None


def _decode_record(doc: JsonData, shape: RecordShape, path: str) -> object:
    cls, fields = shape.cls, shape.fields
    obj = _object(doc, path)
    wanted = {n for n, _ in fields}
    missing = sorted(wanted - obj.keys())
    extra = sorted(obj.keys() - wanted)
    if missing:
        raise WireDecodeError(f"{path}: missing field {', '.join(missing)}")
    if extra:
        raise WireDecodeError(f"{path}: unknown field {', '.join(extra)}")
    values = {n: _decode(obj[n], shape_of(h), f"{path}.{n}") for n, h in fields}
    try:
        return cls(**values)
    except (TypeError, ValueError) as refusal:
        raise WireDecodeError(
            f"{path}: {cls.__qualname__} refuses these values: {refusal}"
        ) from None


def _decode_fixed(
    doc: JsonData, shape: FixedTupleShape, path: str
) -> tuple[object, ...]:
    items = shape.items
    array = _array(doc, path)
    if len(array) != len(items):
        raise WireDecodeError(f"{path}: expected {len(items)} items, got {len(array)}")
    return tuple(
        _decode(d, shape_of(h), f"{path}[{i}]")
        for i, (d, h) in enumerate(zip(array, items, strict=True))
    )


def _decode_union(doc: JsonData, shape: UnionShape, path: str) -> object:
    members = shape.members
    obj = dict(_object(doc, path))
    tag = obj.pop(TYPE_KEY, None)
    for name, cls in members:
        if tag == name:
            return _decode(obj, shape_of(cls), f"{path}<{name}>")
    known = ", ".join(n for n, _ in members)
    raise WireDecodeError(
        f"{path}: unknown wire name {tag!r}; this build knows {known}"
    )


_DECODERS: dict[type, Callable[[Any, Any, str], object]] = {
    ScalarShape: _decode_scalar,
    EnumShape: _decode_enum,
    RecordShape: _decode_record,
    OptionalShape: _decode_optional,
    ItemsShape: _decode_items,
    FixedTupleShape: _decode_fixed,
    MappingShape: _decode_mapping,
    UnionShape: _decode_union,
}


def _object(doc: JsonData, path: str) -> dict[str, object]:
    if type(doc) is not dict:
        raise WireDecodeError(f"{path}: expected an object, got {_describe(doc)}")
    return doc


def _array(doc: JsonData, path: str) -> list[object]:
    if type(doc) is not list:
        raise WireDecodeError(f"{path}: expected an array, got {_describe(doc)}")
    return doc


def _sequence(value: object) -> tuple[object, ...]:
    if not isinstance(value, tuple):
        raise _wrong_class(value, "tuple")
    return value


def _mapping(value: object) -> dict[object, object]:
    if not hasattr(value, "items"):
        raise _wrong_class(value, "mapping")
    return dict(value.items())  # type: ignore[attr-defined]


def _text_key(key: object) -> str:
    if type(key) is not str:
        raise WireSchemaError(f"a mapping crosses the wire with text keys, not {key!r}")
    return key


def _wrong_class(value: object, expected: str) -> WireSchemaError:
    return WireSchemaError(f"expected {expected}, got {type(value).__qualname__}")


def _describe(doc: object) -> str:
    return f"{type(doc).__name__} {json.dumps(doc, default=str)[:40]}"
