"""`EPIC-028G` — the two pieces both desks' estimates share: the fee, and
the largest step-multiple within a budget."""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_estimates import (
    estimated_fee,
    largest_fitting_quantity,
)

_STEP = Decimal("0.001")


def test_the_fee_is_quantity_times_price_times_rate() -> None:
    assert estimated_fee(Decimal("0.5"), Decimal(40000), Decimal("0.0005")) == 10


def test_a_zero_quantity_pays_no_fee() -> None:
    assert estimated_fee(Decimal(0), Decimal(40000), Decimal("0.0005")) == 0


def test_a_budget_that_pays_exactly_n_steps_buys_n_steps() -> None:
    assert largest_fitting_quantity(Decimal(100), Decimal(50), _STEP) == Decimal("0.5")


def test_a_budget_a_hair_short_buys_one_step_less() -> None:
    assert largest_fitting_quantity(
        Decimal(100), Decimal("49.99999"), _STEP
    ) == Decimal("0.499")


def test_a_budget_below_one_step_buys_nothing() -> None:
    assert largest_fitting_quantity(Decimal(100), Decimal("0.0999"), _STEP) == 0
    assert largest_fitting_quantity(Decimal(100), Decimal(0), _STEP) == 0


@pytest.mark.parametrize(
    ("unit_cost", "budget", "step"),
    [
        # PR #300 review: a budget from a non-terminating division came out one
        # step short before the boundary correction.
        (
            Decimal("744.2994") + Decimal("744.2994") * Decimal("0.0005") * 75,
            Decimal(146933827) / Decimal(3000),
            Decimal("0.0001"),
        ),
        # The quotient rounds up onto a step the budget cannot pay.
        (
            Decimal("244197.059"),
            Decimal("78555019.31853299999999999999"),
            Decimal("0.001"),
        ),
        # The quotient rounds down off a step the budget pays exactly.
        (
            Decimal(37471) / Decimal(13),
            Decimal(37471) / Decimal(13) * Decimal("714.339"),
            Decimal("0.001"),
        ),
        (Decimal(3) / Decimal(7), Decimal(10) / Decimal(3), Decimal("0.00001")),
        (Decimal("0.0712"), Decimal(100), Decimal(1)),
        (Decimal(40020), Decimal("1234.56"), _STEP),
    ],
)
def test_the_answer_fits_and_one_more_step_does_not(
    unit_cost: Decimal, budget: Decimal, step: Decimal
) -> None:
    quantity = largest_fitting_quantity(unit_cost, budget, step)

    assert quantity % step == 0
    assert quantity * unit_cost <= budget
    assert (quantity + step) * unit_cost > budget


@pytest.mark.parametrize(
    "bad", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity"), Decimal(-1)]
)
def test_an_amount_that_is_not_a_real_non_negative_number_is_refused(
    bad: Decimal,
) -> None:
    with pytest.raises(ValueError):
        estimated_fee(bad, Decimal(1), Decimal(0))
    with pytest.raises(ValueError):
        estimated_fee(Decimal(1), Decimal(1), bad)
    with pytest.raises(ValueError):
        largest_fitting_quantity(Decimal(1), bad, _STEP)


@pytest.mark.parametrize("bad", [Decimal(0), Decimal(-1), Decimal("NaN")])
def test_a_price_unit_cost_or_step_that_is_not_positive_is_refused(
    bad: Decimal,
) -> None:
    with pytest.raises(ValueError, match="price"):
        estimated_fee(Decimal(1), bad, Decimal(0))
    with pytest.raises(ValueError, match="unit_cost"):
        largest_fitting_quantity(bad, Decimal(1), _STEP)
    with pytest.raises(ValueError, match="step_size"):
        largest_fitting_quantity(Decimal(1), Decimal(1), bad)
