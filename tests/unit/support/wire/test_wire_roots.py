"""`EPIC-047A` — the registry is the closed list: a message names a root of this build or is refused,
and a graph that could carry a secret never registers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.wire_root import WireRoot
from Sagittarius_Elite_Warrior.src.support.wire.wire_errors import (
    WireDecodeError,
    WireSchemaError,
)
from Sagittarius_Elite_Warrior.src.support.wire.wire_roots import WireRoots, revision_of


@dataclass(frozen=True, slots=True)
class Quote:
    price: Decimal


@dataclass(frozen=True, slots=True)
class Keyed:
    api_key: str


@dataclass(frozen=True, slots=True)
class Wrapper:
    inner: tuple[Keyed, ...]


@dataclass(frozen=True, slots=True)
class WithPassword:
    password_hint: str


def _roots() -> WireRoots:
    return WireRoots([WireRoot("sew.test-quote/1", Quote)])


def test_a_message_names_its_root_and_comes_back_equal() -> None:
    doc = _roots().encode("sew.test-quote/1", Quote(Decimal("0.10")))
    assert doc == {"schema": "sew.test-quote/1", "data": {"price": "0.10"}}
    assert _roots().decode(json.loads(json.dumps(doc))) == Quote(Decimal("0.10"))


def test_a_message_of_an_unlisted_name_is_refused() -> None:
    with pytest.raises(WireDecodeError, match=r"unknown wire name 'sew\.test-other/1'"):
        _roots().decode({"schema": "sew.test-other/1", "data": {}})


def test_a_value_cannot_be_sent_under_an_unlisted_name() -> None:
    with pytest.raises(WireSchemaError, match="unknown wire name"):
        _roots().encode("sew.test-other/1", Quote(Decimal(1)))


@pytest.mark.parametrize(
    "doc",
    [[], {"schema": "sew.test-quote/1"}, {"data": {}}, {"schema": 3, "data": {}}],
    ids=["list", "no-data", "no-schema", "schema-number"],
)
def test_a_malformed_envelope_is_a_decode_error(doc: object) -> None:
    with pytest.raises(WireDecodeError):
        _roots().decode(doc)


def test_an_envelope_with_an_extra_key_is_refused() -> None:
    doc = {"schema": "sew.test-quote/1", "data": {"price": "1"}, "note": "x"}
    with pytest.raises(WireDecodeError, match="note"):
        _roots().decode(doc)


@pytest.mark.parametrize(
    "hint", [Keyed, Wrapper, WithPassword], ids=["direct", "nested", "password"]
)
def test_a_graph_with_a_secret_named_field_does_not_register(hint: object) -> None:
    with pytest.raises(WireSchemaError, match="secret"):
        WireRoots([WireRoot("sew.test-bad/1", hint)])


def test_two_roots_cannot_share_a_name() -> None:
    with pytest.raises(WireSchemaError, match="share"):
        WireRoots(
            [WireRoot("sew.test-quote/1", Quote), WireRoot("sew.test-quote/1", Quote)]
        )


@pytest.mark.parametrize("name", ["quote", "sew.Quote/1", "sew.quote", "sew.quote/x"])
def test_a_root_name_has_the_shape_of_a_wire_name(name: str) -> None:
    with pytest.raises(WireSchemaError, match="sew.some-words/1"):
        WireRoots([WireRoot(name, Quote)])


def test_a_revision_travels_in_the_envelope() -> None:
    doc = _roots().encode("sew.test-quote/1", Quote(Decimal(1)), revision=7)
    assert revision_of(json.loads(json.dumps(doc))) == 7
    assert _roots().decode(doc) == Quote(Decimal(1))
    assert revision_of(_roots().encode("sew.test-quote/1", Quote(Decimal(1)))) is None


@pytest.mark.parametrize("revision", [-1, "3", 1.5, True], ids=str)
def test_a_revision_is_a_whole_number(revision: object) -> None:
    with pytest.raises(WireDecodeError, match="revision"):
        revision_of({"schema": "x", "data": {}, "revision": revision})
