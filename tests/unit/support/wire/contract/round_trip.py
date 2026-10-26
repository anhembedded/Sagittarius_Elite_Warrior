"""`EPIC-047A` — what one root's contract test asserts, so every root asserts the same things.

A contract test hands a root's name and its instances here. The helper sends each through the
real registry and JSON text, and proves four things:

1. the value comes back equal and **of the same form** — an enum is still its enum (a `str`
   enum left as text compares equal), a `Decimal` keeps its digits (`12.3400` is not `12.34`),
   a datetime keeps its offset;
2. the wire object of every record holds exactly the record's fields, none more, none fewer
   (the drift lock: a field added to a type is on the wire, or this fails);
3. the *full* instances together leave no field of any record `None` or empty — so a field
   added with a `None` default fails here until the instance that proves it travels is built;
4. a union root's instances cover every member of the union.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterable, Mapping
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.contracts.wire_name import wire_name_of
from Sagittarius_Elite_Warrior.src.shell.wire_roots import link_roots
from Sagittarius_Elite_Warrior.src.support.wire.wire_shape import UnionShape, shape_of

ROOTS = link_roots()
_TYPE_KEY = "$type"


def assert_round_trips(root: str, value: object) -> None:
    """`value` crosses the wire under `root` and comes back equal and of the same form."""
    doc = ROOTS.encode(root, value, revision=1)
    text = json.dumps(doc, allow_nan=False)
    assert ROOTS.schema_of(json.loads(text)) == root
    back = ROOTS.decode(json.loads(text))
    assert back == value
    _same_form(value, back, root)
    _every_field_on_the_wire(value, doc["data"], root)


def assert_full_leaves_no_field_empty(values: Iterable[object]) -> None:
    """Across `values`, every field of every record is set (not `None`, not an empty tuple or mapping)."""
    seen: dict[tuple[type, str], bool] = {}
    for value in values:
        _note_fields(value, seen)
    empty = sorted(
        f"{cls.__qualname__}.{name}" for (cls, name), set_ in seen.items() if not set_
    )
    assert not empty, f"no full instance sets: {', '.join(empty)}"


def assert_union_root_covers_every_member(root: str, values: Iterable[object]) -> None:
    shape = shape_of(ROOTS.hint_of(root))
    assert isinstance(shape, UnionShape), f"{root} is not a union"
    expected = {cls for _, cls in shape.members}
    assert {type(v) for v in values} == expected


def _note_fields(value: object, seen: dict[tuple[type, str], bool]) -> None:
    if isinstance(value, tuple):
        for item in value:
            _note_fields(item, seen)
    elif isinstance(value, Mapping):
        for item in value.values():
            _note_fields(item, seen)
    elif dataclasses.is_dataclass(value):
        for f in dataclasses.fields(value):
            field_value = getattr(value, f.name)
            is_set = field_value is not None and not (
                isinstance(field_value, tuple | Mapping) and len(field_value) == 0
            )
            key = (type(value), f.name)
            seen[key] = seen.get(key, False) or is_set
            _note_fields(field_value, seen)


def _same_form(sent: object, got: object, path: str) -> None:
    assert type(sent) is type(got) or (
        isinstance(sent, Mapping) and isinstance(got, Mapping)
    ), f"{path}: sent {type(sent).__name__}, got {type(got).__name__}"
    if isinstance(sent, Decimal) and isinstance(got, Decimal):
        assert sent.as_tuple() == got.as_tuple(), f"{path}: {sent} came back as {got}"
    elif isinstance(sent, datetime) and isinstance(got, datetime):
        assert sent.isoformat() == got.isoformat(), f"{path}: {sent} came back as {got}"
    elif isinstance(sent, tuple) and isinstance(got, tuple):
        assert len(sent) == len(got)
        for i, (a, b) in enumerate(zip(sent, got, strict=True)):
            _same_form(a, b, f"{path}[{i}]")
    elif isinstance(sent, Mapping) and isinstance(got, Mapping):
        assert dict(sent) == dict(got)
    elif dataclasses.is_dataclass(sent):
        for f in dataclasses.fields(sent):
            _same_form(getattr(sent, f.name), getattr(got, f.name), f"{path}.{f.name}")


def _every_field_on_the_wire(value: object, data: object, path: str) -> None:
    if isinstance(value, tuple):
        assert isinstance(data, list)
        for i, (item, doc) in enumerate(zip(value, data, strict=True)):
            _every_field_on_the_wire(item, doc, f"{path}[{i}]")
    elif dataclasses.is_dataclass(value):
        assert isinstance(data, dict), f"{path}: a record is an object"
        names = {f.name for f in dataclasses.fields(value)}
        keys = set(data) - ({_TYPE_KEY} if wire_name_of(type(value)) else set())
        assert keys == names, (
            f"{path}: wire has {sorted(keys ^ names)} apart from the record's fields"
        )
        for name in names:
            _every_field_on_the_wire(getattr(value, name), data[name], f"{path}.{name}")
