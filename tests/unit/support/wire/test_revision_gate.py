"""`EPIC-047A` — a receiver applies a bot's record only when its revision is greater, so the order in
which a snapshot and an event arrive does not change the result (D5)."""

from __future__ import annotations

import itertools
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.support.wire.revision_gate import RevisionGate
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.round_trip import ROOTS
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_bots import (
    full_bot,
    minimal_bot,
)

_BOT = "sew.bot-snapshot/1"


def test_a_greater_revision_replaces_and_a_lesser_or_equal_one_does_not() -> None:
    gate: RevisionGate[str] = RevisionGate()
    assert gate.offer("b1", 5, "five") is True
    assert gate.offer("b1", 4, "four") is False
    assert gate.offer("b1", 5, "five again") is False
    assert gate.offer("b1", 6, "six") is True
    assert gate.value_of("b1") == "six"
    assert gate.revision_of("b1") == 6


def test_each_bot_has_its_own_revision() -> None:
    gate: RevisionGate[str] = RevisionGate()
    gate.offer("b1", 9, "one")
    assert gate.offer("b2", 1, "two") is True
    assert gate.revision_of("b2") == 1
    assert gate.value_of("b3") is None
    assert gate.revision_of("b3") is None


def test_an_event_that_overtakes_the_snapshot_gives_the_same_result_in_either_order() -> (
    None
):
    """The snapshot (revision 3) is read before the event (revision 4), but the event arrives first."""
    snapshot = ROOTS.encode(_BOT, minimal_bot(), revision=3)
    event = ROOTS.encode(_BOT, full_bot(), revision=4)
    results = []
    for order in itertools.permutations([snapshot, event]):
        gate = RevisionGate()
        for doc in order:
            gate.offer("b-0001", doc["revision"], ROOTS.decode(doc))
        results.append((gate.value_of("b-0001"), gate.revision_of("b-0001")))
    assert results[0] == results[1] == (full_bot(), 4)


def test_a_deleted_bot_is_not_brought_back_by_a_late_snapshot() -> None:
    gate: RevisionGate[str] = RevisionGate()
    gate.offer("b1", 2, "alive")
    assert gate.offer("b1", 3, None) is True
    assert gate.value_of("b1") is None
    assert gate.offer("b1", 2, "alive") is False
    assert gate.value_of("b1") is None
    assert gate.revision_of("b1") == 3


@pytest.mark.parametrize("revision", [-1, True, 1.5], ids=str)
def test_a_revision_is_a_whole_number_from_zero(revision: object) -> None:
    gate: RevisionGate[str] = RevisionGate()
    with pytest.raises(ValueError, match="revision"):
        gate.offer("b1", revision, "x")  # type: ignore[arg-type]


def test_the_first_offer_at_revision_zero_is_applied() -> None:
    gate: RevisionGate[Decimal] = RevisionGate()
    assert gate.offer("b1", 0, Decimal("0.10")) is True
