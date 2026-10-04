"""`EPIC-029E` — every bot market order is sliced under the cap (ADR D21, §3.4).

The task's own figure: an exit of 5,000 USDT at a 500 cap is ten slices.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.market_slices import (
    base_slices,
    quote_slices,
)

CAP = Decimal(500)


def test_a_quote_amount_is_cut_into_slices_no_larger_than_the_cap() -> None:
    assert quote_slices(Decimal(5000), CAP) == (CAP,) * 10
    assert quote_slices(Decimal(1250), CAP) == (CAP, CAP, Decimal(250))
    assert quote_slices(Decimal(500), CAP) == (CAP,)
    assert quote_slices(Decimal("500.01"), CAP) == (CAP, Decimal("0.01"))
    assert quote_slices(Decimal(0), CAP) == ()


def test_an_exit_of_5000_usdt_is_ten_slices_each_within_the_cap() -> None:
    price = Decimal(50000)
    slices = base_slices(Decimal("0.1"), price, CAP, Decimal("0.00001"))

    assert slices == (Decimal("0.01"),) * 10
    assert all(piece * price <= CAP for piece in slices)


def test_a_slice_is_rounded_down_so_it_never_exceeds_the_cap() -> None:
    price = Decimal(30000)
    slices = base_slices(Decimal("0.05"), price, CAP, Decimal("0.0001"))

    assert all(piece * price <= CAP for piece in slices)
    assert sum(slices) == Decimal("0.05")
    assert slices[0] == Decimal("0.0166")


def test_a_remainder_below_one_step_is_not_sent() -> None:
    slices = base_slices(Decimal("0.010009"), Decimal(50000), CAP, Decimal("0.0001"))

    assert sum(slices) == Decimal("0.0100")


@pytest.mark.parametrize("cap", [Decimal(0), Decimal(-1)])
def test_a_cap_that_is_not_positive_is_refused(cap: Decimal) -> None:
    with pytest.raises(ValueError, match="positive"):
        quote_slices(Decimal(10), cap)


def test_a_step_worth_more_than_the_cap_is_refused() -> None:
    with pytest.raises(ValueError, match="worth more than the cap"):
        base_slices(Decimal(1), Decimal(1000), CAP, Decimal(1))
