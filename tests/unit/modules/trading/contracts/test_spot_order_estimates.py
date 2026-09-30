"""`EPIC-028G` — a Spot buy's cost and maximum."""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_order_estimates import (
    SpotOrderTerms,
    spot_buy_cost,
    spot_max_buy_quantity,
)

_TERMS = SpotOrderTerms(price=Decimal(40000), fee_rate=Decimal("0.001"))
_STEP = Decimal("0.00001")


def test_a_buy_costs_its_notional_plus_its_fee_in_the_quote() -> None:
    # 0.5 × 40 000 = 20 000; the 0.1 % fee is 20.
    assert spot_buy_cost(Decimal("0.5"), _TERMS) == Decimal(20020)


def test_a_balance_that_pays_exactly_the_cost_buys_exactly_that_quantity() -> None:
    assert spot_max_buy_quantity(Decimal(20020), _TERMS, _STEP) == Decimal("0.5")


def test_a_balance_a_hair_short_buys_one_step_less() -> None:
    assert spot_max_buy_quantity(Decimal("20019.99"), _TERMS, _STEP) == Decimal(
        "0.49999"
    )


@pytest.mark.parametrize(
    ("available", "terms"),
    [
        (Decimal("1234.56"), _TERMS),
        (Decimal(100) / Decimal(3), SpotOrderTerms(Decimal("0.0712"), Decimal(0))),
        (Decimal("99999.99"), SpotOrderTerms(Decimal("2650.37"), Decimal("0.00075"))),
    ],
)
def test_the_maximum_fits_and_one_more_step_does_not(
    available: Decimal, terms: SpotOrderTerms
) -> None:
    maximum = spot_max_buy_quantity(available, terms, _STEP)

    assert spot_buy_cost(maximum, terms) <= available
    assert spot_buy_cost(maximum + _STEP, terms) > available


@pytest.mark.parametrize("bad", [Decimal(0), Decimal(-1), Decimal("NaN")])
def test_a_price_that_is_not_positive_is_refused(bad: Decimal) -> None:
    with pytest.raises(ValueError, match="price"):
        SpotOrderTerms(price=bad, fee_rate=Decimal(0))


def test_a_negative_fee_rate_is_refused() -> None:
    with pytest.raises(ValueError, match="fee_rate"):
        SpotOrderTerms(price=Decimal(1), fee_rate=Decimal("-0.0001"))
