"""`EPIC-021C` — `OrderQuantityRoundingPolicy`. Boundary-value tests
(`testing-rule.md` §2) plus a mutation-verify: swapping "round down" for
"round to nearest" must turn at least one of these red, or the test proves
nothing (`BOT-106A`'s lesson)."""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.domain.policies.order_quantity_rounding_policy import (
    NotionalCheck,
    OrderQuantityRoundingPolicy,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide

policy = OrderQuantityRoundingPolicy()


# ---------------------------------------------------------------------------
# round_quantity_down
# ---------------------------------------------------------------------------


def test_rounds_down_to_the_nearest_step():
    assert policy.round_quantity_down(Decimal("0.0137"), Decimal("0.001")) == Decimal(
        "0.013"
    )


def test_a_quantity_exactly_on_a_step_boundary_is_unchanged():
    assert policy.round_quantity_down(Decimal("0.013"), Decimal("0.001")) == Decimal(
        "0.013"
    )


def test_a_quantity_one_unit_below_a_step_still_rounds_down_to_the_lower_step():
    """The step immediately below the boundary — proves this isn't
    accidentally rounding to nearest, which would round this one UP."""
    assert policy.round_quantity_down(
        Decimal("0.0139999"), Decimal("0.001")
    ) == Decimal("0.013")


def test_a_quantity_below_the_smallest_step_rounds_to_zero_not_negative():
    assert policy.round_quantity_down(Decimal("0.0005"), Decimal("0.001")) == Decimal(0)


def test_zero_step_size_leaves_the_quantity_unchanged():
    """No exchange filter to round against — a step_size of 0 must not
    divide by zero or silently zero out the quantity."""
    assert policy.round_quantity_down(Decimal("0.0137"), Decimal(0)) == Decimal(
        "0.0137"
    )


def test_precision_from_zero_to_eight_decimal_places():
    assert policy.round_quantity_down(Decimal("123.7"), Decimal(1)) == Decimal(123)
    assert policy.round_quantity_down(
        Decimal("0.00000019"), Decimal("0.00000001")
    ) == Decimal("0.00000019")


def test_mutation_verify_round_to_nearest_would_disagree_with_round_down():
    """Proves the boundary test above actually distinguishes the two
    behaviours: were this policy to round to nearest instead of down,
    0.0139999 would round to 0.014, not 0.013."""
    quantity = Decimal("0.0139999")
    step = Decimal("0.001")
    round_down_result = policy.round_quantity_down(quantity, step)
    round_to_nearest_result = (quantity / step).to_integral_value() * step
    assert round_down_result != round_to_nearest_result


# ---------------------------------------------------------------------------
# round_price_to_tick
# ---------------------------------------------------------------------------


def test_buy_rounds_down_never_paying_more_than_intended():
    result = policy.round_price_to_tick(
        Decimal("64000.07"), Decimal("0.10"), OrderSide.BUY
    )
    assert result == Decimal("64000.00")
    assert result <= Decimal("64000.07")


def test_sell_rounds_up_never_receiving_less_than_intended():
    result = policy.round_price_to_tick(
        Decimal("64000.07"), Decimal("0.10"), OrderSide.SELL
    )
    assert result == Decimal("64000.10")
    assert result >= Decimal("64000.07")


def test_a_price_exactly_on_a_tick_is_unchanged_for_both_sides():
    assert policy.round_price_to_tick(
        Decimal("64000.10"), Decimal("0.10"), OrderSide.BUY
    ) == Decimal("64000.10")
    assert policy.round_price_to_tick(
        Decimal("64000.10"), Decimal("0.10"), OrderSide.SELL
    ) == Decimal("64000.10")


def test_zero_tick_size_leaves_the_price_unchanged():
    assert policy.round_price_to_tick(
        Decimal("64000.07"), Decimal(0), OrderSide.BUY
    ) == Decimal("64000.07")


# ---------------------------------------------------------------------------
# is_notional_sufficient
# ---------------------------------------------------------------------------


def test_notional_exactly_at_the_minimum_is_sufficient():
    assert (
        policy.is_notional_sufficient(Decimal(1), Decimal(100), Decimal(100))
        is NotionalCheck.SUFFICIENT
    )


def test_notional_one_cent_below_the_minimum_is_insufficient():
    assert (
        policy.is_notional_sufficient(Decimal("0.9999"), Decimal(100), Decimal(100))
        is NotionalCheck.INSUFFICIENT
    )


def test_notional_one_cent_above_the_minimum_is_sufficient():
    assert (
        policy.is_notional_sufficient(Decimal("1.0001"), Decimal(100), Decimal(100))
        is NotionalCheck.SUFFICIENT
    )


def test_the_taskfile_worked_example_end_to_end():
    """`EPIC-021C` §5's own worked example, reproduced exactly."""
    step_size = Decimal("0.001")

    accepted_qty = policy.round_quantity_down(Decimal("0.0137"), step_size)
    assert accepted_qty == Decimal("0.013")
    assert (
        policy.is_notional_sufficient(accepted_qty, Decimal(64000), Decimal(100))
        is NotionalCheck.SUFFICIENT
    )

    rejected_qty = policy.round_quantity_down(Decimal("0.0011"), step_size)
    assert rejected_qty == Decimal("0.001")
    assert (
        policy.is_notional_sufficient(rejected_qty, Decimal(64000), Decimal(100))
        is NotionalCheck.INSUFFICIENT
    )
