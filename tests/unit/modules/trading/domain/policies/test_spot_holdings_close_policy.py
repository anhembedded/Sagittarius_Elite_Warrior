"""`EPIC-027M` — `sellable_spot_quantity()`: how much of one Spot asset
Emergency Stop may sell. Pure function, no network — the arithmetic
`EmergencyStopCommandHandler._sell_spot_surplus_holdings()` composes."""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.spot_holdings_close_policy import (
    sellable_spot_quantity,
)


def test_no_surplus_when_current_equals_baseline() -> None:
    """The exact case AC3 protects: nothing above the baseline means
    nothing to sell."""
    assert sellable_spot_quantity(
        Decimal("0.5"), Decimal("0.5"), Decimal("0.001")
    ) == Decimal(0)


def test_never_negative_when_current_is_below_baseline() -> None:
    """`EPIC-027M` AC3 — a holding that shrank below its own baseline (sold
    by hand outside this app, or a fee taken from it) has nothing left for
    this app to sell; the answer must be zero, never a negative quantity."""
    assert sellable_spot_quantity(
        Decimal("0.3"), Decimal("0.5"), Decimal("0.001")
    ) == Decimal(0)


def test_full_surplus_when_baseline_is_zero() -> None:
    """An asset with no baseline entry (never held at Enable time) — every
    unit acquired afterward is fair game."""
    assert sellable_spot_quantity(
        Decimal("1.000"), Decimal(0), Decimal("0.001")
    ) == Decimal("1.000")


def test_surplus_floors_to_the_lot_step() -> None:
    """`0.0015` surplus at a `0.001` step floors to `0.001`, not `0.002` —
    mutation check: swapping floor for ceiling/round would return `0.002`."""
    result = sellable_spot_quantity(Decimal("1.0015"), Decimal("1.0"), Decimal("0.001"))
    assert result == Decimal("0.001")


def test_surplus_smaller_than_one_step_floors_to_zero_dust() -> None:
    """A real surplus exists but is smaller than the exchange's own lot
    step — reported as dust by the caller, never as a fractional order."""
    result = sellable_spot_quantity(Decimal("1.0005"), Decimal("1.0"), Decimal("0.001"))
    assert result == Decimal(0)


def test_boundary_surplus_exactly_one_step_is_sellable() -> None:
    """Boundary value analysis: exactly one step of surplus is sellable in
    full, not floored away — the `<= 0` guard must not also swallow a
    positive surplus equal to the step."""
    result = sellable_spot_quantity(Decimal("1.001"), Decimal("1.0"), Decimal("0.001"))
    assert result == Decimal("0.001")
