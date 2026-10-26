"""`EPIC-047A` — the hash the handshake compares reads wire names and shapes, never Python paths.

R6 (`DERISK.md` §6.4) built a hash over module paths: the same fields in a class made in
another module gave another hash, so moving a class would have refused every desktop with the
wire unchanged. These tests move a class and change the wire one thing at a time.
"""

from __future__ import annotations

from dataclasses import make_dataclass
from decimal import Decimal
from enum import Enum

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.wire_name import wire_name
from Sagittarius_Elite_Warrior.src.core.contracts.wire_root import WireRoot
from Sagittarius_Elite_Warrior.src.support.wire.wire_errors import WireSchemaError
from Sagittarius_Elite_Warrior.src.support.wire.wire_roots import WireRoots

_ROOT = "sew.test-order/1"


def _roots(
    *,
    module: str = "somewhere.first",
    qty_name: str = "qty",
    qty_type: type = Decimal,
    sides: tuple[str, ...] = ("buy", "sell"),
    ok_name: str = "sew.test-ok/1",
    extra: bool = False,
) -> WireRoots:
    """One root, a record holding a typed field, an enum and a two-member union."""
    side = Enum("Side", {s.upper(): s for s in sides}, type=str)
    ok = wire_name(ok_name)(
        make_dataclass("Ok", [("price", Decimal)], frozen=True, module=module)
    )
    failed = wire_name("sew.test-failed/1")(
        make_dataclass("Failed", [("words", str)], frozen=True, module=module)
    )
    fields: list[tuple[str, object]] = [
        (qty_name, qty_type),
        ("side", side),
        ("verdict", ok | failed),
    ]
    if extra:
        fields.append(("leverage", int))
    order = make_dataclass("Order", fields, frozen=True, module=module)
    return WireRoots([WireRoot(_ROOT, order)])


def test_the_same_wire_in_classes_of_another_module_hashes_the_same() -> None:
    first = _roots(module="somewhere.first")
    moved = _roots(module="a.different.package.entirely")
    assert first.root_hashes() == moved.root_hashes()
    assert first.contract_hash() == moved.contract_hash()


def test_the_hash_is_a_stable_text_of_fixed_width() -> None:
    hashes = _roots().root_hashes()
    assert set(hashes) == {_ROOT}
    assert len(hashes[_ROOT]) == 16
    assert int(hashes[_ROOT], 16) >= 0
    assert _roots().contract_hash() == _roots().contract_hash()


@pytest.mark.parametrize(
    "change",
    [
        {"extra": True},
        {"qty_name": "quantity"},
        {"qty_type": str},
        {"qty_type": int},
        {"sides": ("buy", "sell", "hold")},
        {"sides": ("buy",)},
        {"ok_name": "sew.test-ok/2"},
    ],
    ids=[
        "field-added",
        "field-renamed",
        "retyped-str",
        "retyped-int",
        "enum-grew",
        "enum-shrank",
        "member-renamed",
    ],
)
def test_a_change_to_the_wire_changes_the_hash(change: dict[str, object]) -> None:
    base = _roots()
    changed = _roots(**change)  # type: ignore[arg-type]
    assert changed.root_hashes()[_ROOT] != base.root_hashes()[_ROOT]
    assert changed.contract_hash() != base.contract_hash()


def test_a_field_with_no_wire_form_does_not_hash() -> None:
    with pytest.raises(WireSchemaError, match="float"):
        _roots(qty_type=float)


def test_the_wire_names_of_a_registry_are_its_roots_and_its_union_members() -> None:
    assert _roots().wire_names() == ("sew.test-failed/1", "sew.test-ok/1", _ROOT)
