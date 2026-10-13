"""`EPIC-039K` — the liquidation price of a held position: one formula, trading's.

The replay's use of it is `test_grid_futures_liquidation.py`.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.policies.margin_risk_policy import (
    MarginRiskPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_liquidation import (
    HeldPosition,
    Leveraged,
    distance_to_liquidation,
    isolated_margin,
    liquidation_price,
    loss_of_liquidation,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBracket,
    LeverageBrackets,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.futures_replay_builders import (
    BRACKETS,
)

D = Decimal


# -- the price: one formula ---------------------------------------------------- #


@pytest.mark.parametrize("leverage", [2, 5, 10, 50])
@pytest.mark.parametrize("quantity", [D("0.3"), D("-0.3")])
def test_with_no_maintenance_margin_it_is_the_paper_brokers_formula(
    leverage: int, quantity: Decimal
) -> None:
    """`backtesting`'s `MarginRiskPolicy.liquidation_price` is `entry * (1 -/+ 1/leverage)`,
    which it documents as this formula with a zero maintenance rate and amount. The two agree
    there; they differ only by the maintenance margin, which is why that policy stays as it
    is (its docstring) and nothing here forks the formula."""
    flat = LeverageBrackets(
        "BTCUSDT", (LeverageBracket(1, 125, D(0), D(10**9), D(0), D(0)),)
    )
    held = HeldPosition(quantity, D(65000))

    ours = liquidation_price(held, Leveraged(leverage, flat))

    side = PositionSide.LONG if quantity > 0 else PositionSide.SHORT
    papers = MarginRiskPolicy().liquidation_price(side, float(leverage), 65000.0)
    assert ours is not None and papers is not None
    assert float(ours) == pytest.approx(papers)


def test_the_maintenance_margin_brings_the_price_closer_to_the_entry_than_the_paper_one() -> (
    None
):
    held = HeldPosition(D("0.3"), D(65000))

    with_maintenance = liquidation_price(held, Leveraged(10, BRACKETS))

    assert with_maintenance is not None
    assert D(65000) * D("0.9") < with_maintenance < D(65000)


def test_a_long_at_leverage_one_has_no_liquidation_price() -> None:
    assert (
        liquidation_price(HeldPosition(D("0.3"), D(65000)), Leveraged(1, BRACKETS))
        is None
    )


def test_a_short_at_leverage_one_still_has_one() -> None:
    price = liquidation_price(HeldPosition(D("-0.3"), D(65000)), Leveraged(1, BRACKETS))

    assert price is not None and price > D(65000)


def test_a_flat_position_has_no_price() -> None:
    assert liquidation_price(HeldPosition(D(0), D(0)), Leveraged(5, BRACKETS)) is None


def test_funding_paid_is_taken_from_the_margin_and_brings_the_price_closer() -> None:
    fresh = HeldPosition(D("0.3"), D(65000))
    paid = HeldPosition(D("0.3"), D(65000), funding_paid=D(500))

    assert isolated_margin(paid, 10) == isolated_margin(fresh, 10) - 500
    assert liquidation_price(paid, Leveraged(10, BRACKETS)) > liquidation_price(
        fresh, Leveraged(10, BRACKETS)
    )


def test_the_margin_is_never_negative_whatever_the_funding_paid() -> None:
    drained = HeldPosition(D("0.3"), D(65000), funding_paid=D(10**6))

    assert isolated_margin(drained, 10) == 0


def test_a_higher_bracket_puts_the_price_closer_to_the_entry() -> None:
    small = HeldPosition(D("0.5"), D(65000))  # 32,500: first bracket
    large = HeldPosition(D("5"), D(65000))  # 325,000: third bracket

    near = liquidation_price(small, Leveraged(10, BRACKETS))
    nearer = liquidation_price(large, Leveraged(10, BRACKETS))

    assert near is not None and nearer is not None
    assert D(65000) - nearer < D(65000) - near


def test_the_distance_is_a_fraction_of_the_price_and_zero_past_the_limit() -> None:
    held = HeldPosition(D("0.3"), D(65000))

    assert distance_to_liquidation(D(60000), held, D(54000)) == D(6000) / D(60000)
    assert distance_to_liquidation(D(50000), held, D(54000)) == 0


def test_a_liquidation_loses_exactly_the_margin_whatever_the_close_realised() -> None:
    inside = loss_of_liquidation(D(1000), D(-900))
    gapped = loss_of_liquidation(D(1000), D(-1300))

    assert -900 + inside.realised_adjustment == -1000
    assert -1300 + gapped.realised_adjustment == -1000
    assert inside.margin_lost == gapped.margin_lost == 1000
