"""`EPIC-047A` — the reflective codec turns a contract value into JSON and back equal, and
says in words when it cannot.

The fixture types below stand for what the Bots contracts hold: money as `Decimal`, a
`str` enum, a datetime with an offset, a duration, a tuple, a read-only mapping, an
optional, a `NewType` and a union of records that carry a wire name.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import NewType

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.wire_name import wire_name
from Sagittarius_Elite_Warrior.src.support.wire.wire_codec import decode, encode
from Sagittarius_Elite_Warrior.src.support.wire.wire_errors import (
    WireDecodeError,
    WireSchemaError,
)

Code = NewType("Code", str)


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


@wire_name("sew.test-ok/1")
@dataclass(frozen=True, slots=True)
class Ok:
    price: Decimal


@wire_name("sew.test-failed/1")
@dataclass(frozen=True, slots=True)
class Failed:
    words: str


@dataclass(frozen=True, slots=True)
class Leaf:
    qty: Decimal
    side: Side


@dataclass(frozen=True, slots=True)
class Whole:
    name: str
    count: int
    live: bool
    price: Decimal
    at: datetime
    every: timedelta
    code: Code
    leaf: Leaf
    maybe: Leaf | None
    leaves: tuple[Leaf, ...]
    extras: Mapping[str, str] = field(default_factory=dict)
    verdict: Ok | Failed | None = None


def _whole(**over: object) -> Whole:
    base: dict[str, object] = {
        "name": "grid-1",
        "count": 3,
        "live": True,
        "price": Decimal("12.3400"),
        "at": datetime(2026, 10, 26, 9, 30, tzinfo=timezone(timedelta(hours=7))),
        "every": timedelta(milliseconds=250),
        "code": Code("rate-limited"),
        "leaf": Leaf(Decimal("0.00000100"), Side.SELL),
        "maybe": Leaf(Decimal("1E-8"), Side.BUY),
        "leaves": (Leaf(Decimal(1), Side.BUY), Leaf(Decimal(2), Side.SELL)),
        "extras": {"a": "1"},
        "verdict": Ok(Decimal("0.1")),
    }
    base.update(over)
    return Whole(**base)  # type: ignore[arg-type]


def _over_the_wire(value: Whole) -> Whole:
    text = json.dumps(encode(value, Whole))
    back = decode(json.loads(text), Whole)
    assert isinstance(back, Whole)
    return back


def test_a_full_value_comes_back_equal() -> None:
    value = _whole()
    assert _over_the_wire(value) == value


def test_a_minimal_value_comes_back_equal() -> None:
    value = _whole(maybe=None, leaves=(), extras={}, verdict=None)
    assert _over_the_wire(value) == value


def test_money_is_text_on_the_wire_and_keeps_every_digit() -> None:
    doc = encode(_whole(price=Decimal("12.3400")), Whole)
    assert doc["price"] == "12.3400"
    back = _over_the_wire(_whole(price=Decimal("1E-8")))
    assert back.price == Decimal("1E-8")
    assert str(back.price) == "1E-8"
    assert (0.1 + 0.2) != 0.3  # why a JSON number would be wrong
    summed = _over_the_wire(_whole(price=Decimal("0.30000000000000004"))).price
    assert summed == Decimal("0.30000000000000004")


def test_a_decoded_enum_is_the_enum_not_its_text() -> None:
    back = _over_the_wire(_whole())
    assert type(back.leaf.side) is Side
    assert type(back.price) is Decimal
    assert type(back.at) is datetime
    assert type(back.every) is timedelta


def test_a_datetime_keeps_its_offset_and_a_naive_one_stays_naive() -> None:
    aware = _over_the_wire(_whole())
    assert aware.at.utcoffset() == timedelta(hours=7)
    naive_at = datetime(2026, 1, 2, 3, 4, 5)  # noqa: DTZ001 - the naive datetime under test
    naive = _over_the_wire(_whole(at=naive_at))
    assert naive.at.tzinfo is None
    utc = _over_the_wire(_whole(at=datetime(2026, 1, 2, tzinfo=UTC)))
    assert utc.at.utcoffset() == timedelta(0)


def test_a_union_member_is_tagged_with_its_wire_name_not_its_class() -> None:
    doc = encode(_whole(verdict=Failed("no key")), Whole)
    assert doc["verdict"]["$type"] == "sew.test-failed/1"
    assert _over_the_wire(_whole(verdict=Failed("no key"))).verdict == Failed("no key")


def test_an_unknown_wire_name_is_a_decode_error() -> None:
    doc = encode(_whole(), Whole)
    doc["verdict"]["$type"] = "sew.test-other/1"
    with pytest.raises(WireDecodeError, match=r"verdict.*sew\.test-other/1"):
        decode(doc, Whole)


def test_a_missing_field_is_an_error_never_a_default() -> None:
    doc = encode(_whole(), Whole)
    del doc["extras"]  # the type has a default for it; the wire may not rely on it
    with pytest.raises(WireDecodeError, match="missing.*extras"):
        decode(doc, Whole)


def test_an_unknown_field_is_an_error() -> None:
    doc = encode(_whole(), Whole)
    doc["leverage"] = 3
    with pytest.raises(WireDecodeError, match="leverage"):
        decode(doc, Whole)


@pytest.mark.parametrize(
    ("field_name", "bad"),
    [
        ("name", 3),
        ("count", "3"),
        ("count", True),
        ("live", 1),
        ("price", 12.34),
        ("price", "NaN"),
        ("price", "twelve"),
        ("at", "yesterday"),
        ("every", 0.25),
        ("leaves", {"a": 1}),
        ("leaf", {"qty": "1", "side": "hold"}),
    ],
    ids=lambda p: str(p)[:12],
)
def test_a_wrong_type_is_a_decode_error_naming_the_field(
    field_name: str, bad: object
) -> None:
    doc = encode(_whole(), Whole)
    doc[field_name] = bad
    with pytest.raises(WireDecodeError, match=field_name):
        decode(doc, Whole)


@dataclass(frozen=True, slots=True)
class Pair:
    bounds: tuple[Decimal, Decimal]


@dataclass(frozen=True, slots=True)
class Positive:
    n: int

    def __post_init__(self) -> None:
        if self.n <= 0:
            raise ValueError("n must be positive")


@dataclass(frozen=True, slots=True)
class Loose:
    ratio: float


@dataclass(frozen=True, slots=True)
class Nameless:
    n: int


@dataclass(frozen=True, slots=True)
class Holder:
    what: Ok | Nameless


def test_a_value_the_types_own_rule_rejects_is_a_decode_error() -> None:
    with pytest.raises(WireDecodeError, match="n must be positive"):
        decode({"n": -1}, Positive)


def test_a_float_has_no_wire_form() -> None:
    with pytest.raises(WireSchemaError, match="float"):
        encode(Loose(0.5), Loose)


def test_a_union_member_without_a_wire_name_is_refused() -> None:
    with pytest.raises(WireSchemaError, match="Nameless"):
        encode(Holder(Nameless(1)), Holder)


def test_a_value_of_the_wrong_class_is_an_encode_error() -> None:
    with pytest.raises(WireSchemaError, match="Leaf"):
        encode(Ok(Decimal(1)), Leaf)


def test_a_non_finite_decimal_is_refused_on_encode() -> None:
    with pytest.raises(WireSchemaError, match="finite"):
        encode(Leaf(Decimal("NaN"), Side.BUY), Leaf)


def test_a_fixed_tuple_keeps_its_length() -> None:
    pair = Pair((Decimal("1.5"), Decimal("2.50")))
    doc = encode(pair, Pair)
    assert doc == {"bounds": ["1.5", "2.50"]}
    assert decode(doc, Pair) == pair
    with pytest.raises(WireDecodeError, match="expected 2 items"):
        decode({"bounds": ["1"]}, Pair)


@pytest.mark.parametrize(
    "text",
    [
        "1_0",
        " 1 ",
        "١٢٣",
        "1E999999999",
        "1e-999999999",
        "1e5",
        "+1",
        "0x10",
        "007",
        "1" * 400,
        "",
    ],
    ids=lambda t: repr(t)[:14],
)
def test_a_decimal_that_is_not_what_the_encoder_writes_is_refused(text: str) -> None:
    doc = encode(_whole(), Whole)
    doc["price"] = text
    with pytest.raises(WireDecodeError, match="price"):
        decode(doc, Whole)


@pytest.mark.parametrize("text", ["0", "-0", "12.3400", "1E-8", "1E+2", "0E-8", "-5.5"])
def test_every_text_the_encoder_can_write_for_a_decimal_is_read_back(text: str) -> None:
    value = _whole(price=Decimal(text))
    assert str(_over_the_wire(value).price) == text


@pytest.mark.parametrize(
    "text",
    [
        "20260101",
        "2026-01-01",
        "2026-01-01T00:00:00Z",
        "2026-10-26 09:30:00",
        "2026-10-26T09:30:15.1",
    ],
    ids=lambda t: t[:14],
)
def test_a_datetime_that_is_not_what_the_encoder_writes_is_refused(text: str) -> None:
    doc = encode(_whole(), Whole)
    doc["at"] = text
    with pytest.raises(WireDecodeError, match="at"):
        decode(doc, Whole)
