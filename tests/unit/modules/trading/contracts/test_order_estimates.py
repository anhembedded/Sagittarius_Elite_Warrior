"""`EPIC-028G` — `estimated_fee`, `order_cost` and `max_order_quantity`.

@details Boundary values around every edge the desks rely on: a balance that
pays exactly the maximum, one that falls a hair short, a quantity of zero,
and a step larger than what fits. The maximum is also checked against its
defining property, that its cost fits and one more step does not, over
several terms, rather than against a figure worked out by hand.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_estimates import (
    OrderTerms,
    estimated_fee,
    max_order_quantity,
    order_cost,
)

_FUTURES = OrderTerms(price=Decimal(40000), leverage=10, fee_rate=Decimal("0.0005"))
_SPOT = OrderTerms(price=Decimal(40000), leverage=1, fee_rate=Decimal("0.001"))
_STEP = Decimal("0.001")


def test_the_fee_is_the_notional_times_the_rate() -> None:
    assert estimated_fee(Decimal("0.5"), _FUTURES) == Decimal(10)


def test_a_futures_cost_is_the_initial_margin_plus_the_fee() -> None:
    # 0.5 × 40 000 = 20 000 notional; ÷ 10 = 2 000 margin; fee 10.
    assert order_cost(Decimal("0.5"), _FUTURES) == Decimal(2010)


def test_a_spot_cost_is_the_whole_notional_plus_the_fee() -> None:
    # Leverage 1: 20 000 notional; fee at 0.1 % is 20.
    assert order_cost(Decimal("0.5"), _SPOT) == Decimal(20020)


def test_a_quantity_of_zero_costs_nothing() -> None:
    assert order_cost(Decimal(0), _FUTURES) == 0
    assert estimated_fee(Decimal(0), _FUTURES) == 0


def test_a_balance_that_pays_exactly_the_cost_buys_exactly_that_quantity() -> None:
    assert max_order_quantity(Decimal(2010), _FUTURES, _STEP) == Decimal("0.5")


def test_a_balance_a_hair_short_buys_one_step_less() -> None:
    assert max_order_quantity(Decimal("2009.99"), _FUTURES, _STEP) == Decimal("0.499")


def test_a_balance_that_cannot_pay_one_step_buys_nothing() -> None:
    assert max_order_quantity(Decimal(1), _FUTURES, _STEP) == 0
    assert max_order_quantity(Decimal(0), _FUTURES, _STEP) == 0


@pytest.mark.parametrize(
    ("available", "terms", "step"),
    [
        (Decimal("1234.56"), _FUTURES, _STEP),
        (Decimal("1234.56"), _SPOT, Decimal("0.00001")),
        (
            Decimal(100),
            OrderTerms(Decimal("0.0712"), 20, Decimal("0.0004")),
            Decimal(1),
        ),
        (Decimal("99999.99"), OrderTerms(Decimal("2650.37"), 125, Decimal(0)), _STEP),
    ],
)
def test_the_maximum_fits_and_one_more_step_does_not(
    available: Decimal, terms: OrderTerms, step: Decimal
) -> None:
    maximum = max_order_quantity(available, terms, step)

    assert maximum % step == 0
    assert order_cost(maximum, terms) <= available
    assert order_cost(maximum + step, terms) > available


@pytest.mark.parametrize(
    "bad", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity"), Decimal(-1)]
)
def test_an_amount_that_is_not_a_real_non_negative_number_is_refused(
    bad: Decimal,
) -> None:
    with pytest.raises(ValueError):
        estimated_fee(bad, _FUTURES)
    with pytest.raises(ValueError):
        order_cost(bad, _FUTURES)
    with pytest.raises(ValueError):
        max_order_quantity(bad, _FUTURES, _STEP)
    with pytest.raises(ValueError):
        OrderTerms(price=Decimal(1), leverage=1, fee_rate=bad)


@pytest.mark.parametrize("bad", [Decimal(0), Decimal(-1), Decimal("NaN")])
def test_a_price_or_step_that_is_not_positive_is_refused(bad: Decimal) -> None:
    with pytest.raises(ValueError, match="price"):
        OrderTerms(price=bad, leverage=1, fee_rate=Decimal(0))
    with pytest.raises(ValueError, match="step_size"):
        max_order_quantity(Decimal(100), _FUTURES, bad)


def test_a_leverage_below_one_is_refused_and_one_is_spot() -> None:
    with pytest.raises(ValueError, match="leverage"):
        OrderTerms(price=Decimal(1), leverage=0, fee_rate=Decimal(0))
    assert OrderTerms(price=Decimal(1), leverage=1, fee_rate=Decimal(0)).leverage == 1
