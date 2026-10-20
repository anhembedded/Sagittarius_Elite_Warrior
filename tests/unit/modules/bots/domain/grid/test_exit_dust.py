"""`BOT-190` — what an exit leaves is dust when the stop would not sell it any more."""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.exit_dust import (
    is_exit_dust,
)

D = Decimal
STEP = D("0.00001")
MIN_NOTIONAL = D("5")
PRICE = D("40000")


@pytest.mark.parametrize(
    ("held", "dust"),
    [
        (D("0"), True),
        (D("0.00000948"), True),  # below one market step: no slice can be sent
        (
            D("0.00001"),
            False,
        ),  # one step: a reduce-only close ignores the minimum notional
        (D("0.0214"), False),
        (D("-0.00000948"), True),  # a short's remainder, signed
        (D("-0.0214"), False),
    ],
)
def test_a_position_venue_judges_only_the_market_step(
    held: Decimal, dust: bool
) -> None:
    assert is_exit_dust(held, PRICE, STEP, None) is dust


@pytest.mark.parametrize(
    ("held", "dust"),
    [
        (D("0"), True),
        (D("0.00000948"), True),
        (D("0.00001"), True),  # worth 0.4, below the minimum
        (D("0.000124"), True),  # worth 4.96
        (D("0.000125"), False),  # worth exactly the minimum: the stop sells it
        (D("0.0214"), False),
    ],
)
def test_spot_keeps_a_base_worth_less_than_the_minimum_notional(
    held: Decimal, dust: bool
) -> None:
    assert is_exit_dust(held, PRICE, STEP, MIN_NOTIONAL) is dust


def test_without_a_price_only_the_step_judges() -> None:
    assert is_exit_dust(D("0.00001"), None, STEP, MIN_NOTIONAL) is False
    assert is_exit_dust(D("0.000001"), None, STEP, MIN_NOTIONAL) is True
