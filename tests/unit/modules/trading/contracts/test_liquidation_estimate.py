"""`EPIC-028G` — `estimated_liquidation_price`.

@details Every price is checked against what defines it rather than a
hand-worked figure: at the liquidation price, the margin plus the position's
unrealised PnL equals the maintenance margin Binance requires there
(`Q × LP × MMR − cum`). One long and one short are also pinned to Binance's
isolated-margin closed form as a second, independent check.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.liquidation_estimate import (
    LiquidationTerms,
    estimated_liquidation_price,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)

_MMR = Decimal("0.004")
_TOLERANCE = Decimal("1e-18")


def _terms(
    side: PositionSide,
    margin: Decimal,
    maintenance_amount: Decimal = Decimal(0),
) -> LiquidationTerms:
    return LiquidationTerms(
        side=side,
        quantity=Decimal("0.5"),
        entry_price=Decimal(40000),
        margin=margin,
        maintenance_margin_rate=_MMR,
        maintenance_amount=maintenance_amount,
    )


def _equity_minus_maintenance(terms: LiquidationTerms, price: Decimal) -> Decimal:
    sign = 1 if terms.side is PositionSide.LONG else -1
    pnl = sign * terms.quantity * (price - terms.entry_price)
    maintenance = (
        terms.quantity * price * terms.maintenance_margin_rate
        - terms.maintenance_amount
    )
    return terms.margin + pnl - maintenance


@pytest.mark.parametrize("side", [PositionSide.LONG, PositionSide.SHORT])
@pytest.mark.parametrize(
    ("margin", "maintenance_amount"),
    [
        (Decimal(2000), Decimal(0)),
        (Decimal(500), Decimal(0)),
        (Decimal(2000), Decimal(50)),
    ],
)
def test_at_the_estimate_the_margin_left_equals_the_maintenance_margin(
    side: PositionSide, margin: Decimal, maintenance_amount: Decimal
) -> None:
    terms = _terms(side, margin, maintenance_amount)

    price = estimated_liquidation_price(terms).price

    assert price is not None
    assert abs(_equity_minus_maintenance(terms, price)) < _TOLERANCE


def test_an_isolated_long_matches_binances_closed_form() -> None:
    # Isolated margin at 10x is notional ÷ 10 = 2 000:
    # LP = EP × (1 − 1/L) ÷ (1 − MMR).
    price = estimated_liquidation_price(_terms(PositionSide.LONG, Decimal(2000))).price
    expected = Decimal(40000) * (1 - Decimal("0.1")) / (1 - _MMR)
    assert price is not None
    assert abs(price - expected) < _TOLERANCE


def test_an_isolated_short_matches_binances_closed_form() -> None:
    # LP = EP × (1 + 1/L) ÷ (1 + MMR).
    price = estimated_liquidation_price(_terms(PositionSide.SHORT, Decimal(2000))).price
    expected = Decimal(40000) * (1 + Decimal("0.1")) / (1 + _MMR)
    assert price is not None
    assert abs(price - expected) < _TOLERANCE


def test_a_long_is_liquidated_below_entry_and_a_short_above() -> None:
    long = estimated_liquidation_price(_terms(PositionSide.LONG, Decimal(2000))).price
    short = estimated_liquidation_price(_terms(PositionSide.SHORT, Decimal(2000))).price
    assert long is not None and long < 40000
    assert short is not None and short > 40000


def test_a_long_backed_by_more_than_its_notional_has_no_liquidation_price() -> None:
    # 0.5 × 40 000 = 20 000 notional; 25 000 of margin never runs out.
    estimate = estimated_liquidation_price(_terms(PositionSide.LONG, Decimal(25000)))

    assert estimate.price is None


def test_a_long_backed_by_exactly_its_notional_has_no_liquidation_price() -> None:
    """The boundary: the formula gives a price of zero, which no market
    reaches, so there is no liquidation price to show."""
    estimate = estimated_liquidation_price(_terms(PositionSide.LONG, Decimal(20000)))

    assert estimate.price is None


def test_every_answer_says_it_is_an_estimate() -> None:
    assert estimated_liquidation_price(
        _terms(PositionSide.LONG, Decimal(2000))
    ).is_estimate
    assert estimated_liquidation_price(
        _terms(PositionSide.LONG, Decimal(25000))
    ).is_estimate


@pytest.mark.parametrize(
    "field", ["quantity", "entry_price", "margin", "maintenance_amount"]
)
@pytest.mark.parametrize("bad", [Decimal("NaN"), Decimal("Infinity"), Decimal(-1)])
def test_a_term_that_is_not_a_real_non_negative_number_is_refused(
    field: str, bad: Decimal
) -> None:
    with pytest.raises(ValueError, match=field):
        replace(_terms(PositionSide.LONG, Decimal(1)), **{field: bad})


@pytest.mark.parametrize("field", ["quantity", "entry_price"])
def test_a_zero_quantity_or_entry_price_is_refused(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        replace(_terms(PositionSide.LONG, Decimal(1)), **{field: Decimal(0)})


@pytest.mark.parametrize("rate", [Decimal("-0.001"), Decimal(1), Decimal("NaN")])
def test_a_maintenance_rate_outside_zero_to_one_is_refused(rate: Decimal) -> None:
    with pytest.raises(ValueError, match="maintenance_margin_rate"):
        LiquidationTerms(
            side=PositionSide.LONG,
            quantity=Decimal(1),
            entry_price=Decimal(1),
            margin=Decimal(1),
            maintenance_margin_rate=rate,
        )


def test_a_zero_maintenance_rate_is_accepted() -> None:
    terms = LiquidationTerms(
        side=PositionSide.SHORT,
        quantity=Decimal(1),
        entry_price=Decimal(100),
        margin=Decimal(10),
        maintenance_margin_rate=Decimal(0),
    )
    assert estimated_liquidation_price(terms).price == Decimal(110)
