"""`EPIC-047A` — the canonical description of a root's wire form, and the hash the handshake compares.

A record is described by its field names and their schemas, a tagged union by its members' wire
names, an enum by its members' wire values, a scalar by its wire kind. No Python module path or
class name appears: moving or renaming a class changes nothing, and a change to the wire (a field
added, renamed or retyped, an enum member added, a member's wire name changed) changes the hash.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping

from Sagittarius_Elite_Warrior.src.support.wire.wire_errors import WireSchemaError
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

type Schema = str | dict[str, object]
_HASH_WIDTH = 16


def schema_of(hint: object) -> Schema:
    """The canonical schema of a hint, or a `WireSchemaError` when it has no wire form."""
    return _describe(shape_of(hint), ())


def hash_of_schema(name: str, schema: Schema) -> str:
    """A short, stable digest of one root: its wire name and its schema."""
    return _digest({"root": name, "schema": schema})


def combined_hash(root_hashes: Mapping[str, str]) -> str:
    """One digest over every root's digest, for a log line and a quick "same build" check."""
    return _digest(dict(root_hashes))


def union_member_names(hint: object) -> frozenset[str]:
    """The wire names of every union member reachable from `hint`."""
    names: set[str] = set()
    _collect_members(shape_of(hint), names, set())
    return frozenset(names)


def _digest(document: object) -> str:
    text = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:_HASH_WIDTH]


def _describe(shape: Shape, stack: tuple[type, ...]) -> Schema:
    match shape:
        case ScalarShape(_, kind):
            return kind
        case EnumShape(cls):
            return {"enum": sorted(str(m.value) for m in cls)}
        case RecordShape(cls, fields):
            if cls in stack:
                raise WireSchemaError(
                    f"{cls.__qualname__} holds itself; a wire form is finite"
                )
            inner = (*stack, cls)
            return {"record": {n: _describe(shape_of(h), inner) for n, h in fields}}
        case OptionalShape(item):
            return {"optional": _describe(shape_of(item), stack)}
        case ItemsShape(item):
            return {"items": _describe(shape_of(item), stack)}
        case FixedTupleShape(items):
            return {"tuple": [_describe(shape_of(i), stack) for i in items]}
        case MappingShape(value):
            return {"map": _describe(shape_of(value), stack)}
        case UnionShape(members):
            return {
                "union": {
                    name: _describe(shape_of(cls), stack) for name, cls in members
                }
            }
    raise AssertionError(shape)  # pragma: no cover - the match above is exhaustive


def _collect_members(shape: Shape, names: set[str], seen: set[type]) -> None:
    if isinstance(shape, UnionShape):
        names.update(n for n, _ in shape.members)
    if isinstance(shape, RecordShape):
        if shape.cls in seen:
            return
        seen.add(shape.cls)
    for child in _children(shape):
        _collect_members(child, names, seen)


def _children(shape: Shape) -> Iterable[Shape]:
    match shape:
        case RecordShape(_, fields):
            return [shape_of(h) for _, h in fields]
        case OptionalShape(item) | ItemsShape(item) | MappingShape(item):
            return [shape_of(item)]
        case FixedTupleShape(items):
            return [shape_of(i) for i in items]
        case UnionShape(members):
            return [shape_of(cls) for _, cls in members]
    return []
