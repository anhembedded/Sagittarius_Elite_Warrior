"""`EPIC-039F` - `estimated_liquidation_price_in_brackets`: the same formula, with the
bracket found for the position's own notional.

@details The first bracket's rates would flatter a big position. Raising leverage (less
margin behind the same position) must never move the estimate away from the entry."""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBracket,
    LeverageBrackets,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.liquidation_estimate import (
    BracketedPosition,
    LiquidationTerms,
    estimated_liquidation_price,
    estimated_liquidation_price_in_brackets,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)

D = Decimal
_BRACKETS = LeverageBrackets(
    "BTCUSDT",
    (
        LeverageBracket(1, 125, D(0), D(50_000), D("0.004"), D(0)),
        LeverageBracket(2, 100, D(50_000), D(250_000), D("0.005"), D(50)),
        LeverageBracket(3, 50, D(250_000), D(1_000_000), D("0.01"), D(1_300)),
    ),
)


def _position(side: PositionSide, quantity: str, margin: str) -> BracketedPosition:
    return BracketedPosition(side, D(quantity), D(40_000), D(margin))


def test_a_position_uses_the_bracket_of_its_own_notional_not_the_first() -> None:
    position = _position(PositionSide.LONG, "5", "20000")  # notional 200,000: bracket 2

    estimate = estimated_liquidation_price_in_brackets(position, _BRACKETS)

    expected = estimated_liquidation_price(
        LiquidationTerms(
            PositionSide.LONG, D(5), D(40_000), D(20_000), D("0.005"), D(50)
        )
    )
    first_bracket = estimated_liquidation_price(
        LiquidationTerms(
            PositionSide.LONG, D(5), D(40_000), D(20_000), D("0.004"), D(0)
        )
    )
    assert estimate == expected
    assert estimate.price is not None and first_bracket.price is not None
    assert estimate.price > first_bracket.price  # nearer entry: the first would flatter


@pytest.mark.parametrize("side", list(PositionSide))
def test_raising_leverage_never_moves_the_estimate_away_from_the_entry(
    side: PositionSide,
) -> None:
    previous: Decimal | None = None
    for leverage in range(1, 51):
        position = BracketedPosition(side, D(5), D(40_000), D(5) * D(40_000) / leverage)
        price = estimated_liquidation_price_in_brackets(position, _BRACKETS).price
        if price is None:  # no price liquidates it: furthest possible
            continue
        if previous is not None:
            moved_toward_entry = (
                price > previous if side is PositionSide.LONG else price < previous
            )
            assert moved_toward_entry or price == previous
        previous = price
