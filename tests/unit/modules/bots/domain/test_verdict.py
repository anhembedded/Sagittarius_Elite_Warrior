"""`EPIC-029B` — a verdict's severity, and only REFUSED blocks."""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
    any_refused,
)


def _v(severity: VerdictSeverity) -> Verdict:
    return Verdict(severity, "CODE", "reason", {"value": Decimal(1)})


def test_only_refused_refuses() -> None:
    assert _v(VerdictSeverity.REFUSED).refuses
    assert not _v(VerdictSeverity.WARNING).refuses
    assert not _v(VerdictSeverity.OK).refuses


def test_any_refused() -> None:
    assert not any_refused(())
    assert not any_refused((_v(VerdictSeverity.OK), _v(VerdictSeverity.WARNING)))
    assert any_refused((_v(VerdictSeverity.OK), _v(VerdictSeverity.REFUSED)))


def test_the_numbers_are_frozen() -> None:
    numbers = {"value": Decimal(1)}
    verdict = Verdict(VerdictSeverity.OK, "C", "r", numbers)
    numbers["value"] = Decimal(2)
    assert verdict.numbers["value"] == Decimal(1)
    with pytest.raises(TypeError):
        verdict.numbers["value"] = Decimal(3)  # type: ignore[index]
