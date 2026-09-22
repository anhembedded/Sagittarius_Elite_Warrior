"""`MarginRiskPolicy` — leverage, mark-to-market and PnL realization.

The five sizing cases that used to open this file left with the rule they
tested: `EPIC-025` PR 2.1d (ADR D17) moved
`calculate_margin_and_notional()` into `modules/strategy` as `ISizingPolicy`,
and they are now
`tests/unit/modules/strategy/domain/policies/test_margin_sizing_policy.py`
with their numbers unchanged. Nothing was dropped.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exit_reason import (
    ExitReason,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.policies.margin_risk_policy import (
    MarginRiskPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)


@pytest.fixture
def policy() -> MarginRiskPolicy:
    return MarginRiskPolicy()


@dataclass(frozen=True)
class _FakePosition:
    """Shaped from `ILiquidatablePosition` exactly — the 3 properties
    `evaluate_liquidations` reads, nothing else."""

    side: PositionSide
    leverage: float
    liquidation_price: float | None


def test_get_leverage(policy: MarginRiskPolicy):
    assert policy.get_leverage(PositionSide.LONG, 3.0, 5.0) == 3.0
    assert policy.get_leverage(PositionSide.SHORT, 3.0, 5.0) == 5.0


def test_mark_to_market(policy: MarginRiskPolicy):
    # Unleveraged LONG (1.0x): 10 qty marked at $120 = $1,200
    assert (
        policy.mark_to_market(
            side=PositionSide.LONG,
            leverage=1.0,
            quantity=10.0,
            entry_price=100.0,
            balance_before_entry=1000.0,
            mark_price=120.0,
        )
        == 1200.0
    )

    # Leveraged LONG (3.0x): margin $1,000 + (120 - 100) * 30 qty = $1,000 + $600 = $1,600
    assert (
        policy.mark_to_market(
            side=PositionSide.LONG,
            leverage=3.0,
            quantity=30.0,
            entry_price=100.0,
            balance_before_entry=1000.0,
            mark_price=120.0,
        )
        == 1600.0
    )

    # SHORT: margin $1,000 + (100 - 80) * 10 qty = $1,000 + $200 = $1,200
    assert (
        policy.mark_to_market(
            side=PositionSide.SHORT,
            leverage=1.0,
            quantity=10.0,
            entry_price=100.0,
            balance_before_entry=1000.0,
            mark_price=80.0,
        )
        == 1200.0
    )


def test_calculate_realized_pnl_long_unleveraged(policy: MarginRiskPolicy):
    # Buy 10 qty at $100 ($1,000 margin/spent), exit at $120 ($1,200 notional).
    # Exit fee $1.20. Net proceeds = $1,198.80 -> PnL = $198.80.
    pnl, pnl_pct, balance_release = policy.calculate_realized_pnl(
        side=PositionSide.LONG,
        leverage=1.0,
        quantity=10.0,
        entry_price=100.0,
        exit_price=120.0,
        balance_before_entry=1000.0,
        entry_fee=1.0,
        exit_fee=1.2,
    )
    assert pnl == pytest.approx(198.8)
    assert pnl_pct == pytest.approx(19.88)
    assert balance_release == pytest.approx(1198.8)


def test_liquidation_price_long_unleveraged_is_none(policy: MarginRiskPolicy):
    """BOT-049 — an unleveraged (1.0x) LONG is modeled as spot (same special
    case as `mark_to_market`) and so has no margin to lose."""
    assert policy.liquidation_price(PositionSide.LONG, 1.0, 100.0) is None


def test_liquidation_price_long_leveraged(policy: MarginRiskPolicy):
    # entry 100, 5x -> margin covers a 20% adverse move: 100 * (1 - 1/5) = 80.
    assert policy.liquidation_price(PositionSide.LONG, 5.0, 100.0) == pytest.approx(
        80.0
    )


def test_liquidation_price_short_including_at_1x(policy: MarginRiskPolicy):
    # SHORT is always margined, even at "1x" (BOT-050: no such thing as spot
    # short) -> entry 100, 1x liquidates at a 100% adverse move: 200.
    assert policy.liquidation_price(PositionSide.SHORT, 1.0, 100.0) == pytest.approx(
        200.0
    )
    # 5x -> 100 * (1 + 1/5) = 120.
    assert policy.liquidation_price(PositionSide.SHORT, 5.0, 100.0) == pytest.approx(
        120.0
    )


def test_liquidation_price_matches_the_zero_boundary_of_realized_pnl(
    policy: MarginRiskPolicy,
):
    """The formula's whole justification: exiting exactly at the computed
    liquidation price must realize a balance_release of (approximately) zero
    — the position lost its entire margin, no more, no less. Proves the
    formula is a real algebraic consequence of `calculate_realized_pnl`
    rather than an independently-invented number that happens to look
    plausible (`BOT-049` §3's own stated risk)."""
    entry_price, leverage, quantity = 100.0, 4.0, 40.0
    margin = entry_price * quantity / leverage  # 1_000.0, this policy's own formula

    liq_price = policy.liquidation_price(PositionSide.LONG, leverage, entry_price)
    assert liq_price is not None
    _, _, balance_release = policy.calculate_realized_pnl(
        PositionSide.LONG,
        leverage,
        quantity,
        entry_price,
        liq_price,
        margin,
        entry_fee=0.0,
        exit_fee=0.0,
    )
    assert balance_release == pytest.approx(0.0, abs=1e-9)

    liq_price = policy.liquidation_price(PositionSide.SHORT, leverage, entry_price)
    assert liq_price is not None
    _, _, balance_release = policy.calculate_realized_pnl(
        PositionSide.SHORT,
        leverage,
        quantity,
        entry_price,
        liq_price,
        margin,
        entry_fee=0.0,
        exit_fee=0.0,
    )
    assert balance_release == pytest.approx(0.0, abs=1e-9)


def test_evaluate_liquidations_triggers_long_when_low_reaches_it(
    policy: MarginRiskPolicy,
):
    pos = _FakePosition(side=PositionSide.LONG, leverage=5.0, liquidation_price=80.0)

    triggered, still_open = policy.evaluate_liquidations([pos], high=101.0, low=79.0)

    assert still_open == []
    assert len(triggered) == 1
    assert triggered[0] == (pos, 80.0, ExitReason.LIQUIDATION)


def test_evaluate_liquidations_leaves_position_open_when_not_reached(
    policy: MarginRiskPolicy,
):
    pos = _FakePosition(side=PositionSide.LONG, leverage=5.0, liquidation_price=80.0)

    triggered, still_open = policy.evaluate_liquidations([pos], high=101.0, low=81.0)

    assert triggered == []
    assert still_open == [pos]


def test_evaluate_liquidations_triggers_short_when_high_reaches_it(
    policy: MarginRiskPolicy,
):
    pos = _FakePosition(side=PositionSide.SHORT, leverage=5.0, liquidation_price=120.0)

    triggered, still_open = policy.evaluate_liquidations([pos], high=121.0, low=99.0)

    assert still_open == []
    assert triggered == [(pos, 120.0, ExitReason.LIQUIDATION)]


def test_evaluate_liquidations_never_triggers_a_position_with_no_liquidation_price(
    policy: MarginRiskPolicy,
):
    """An unleveraged LONG (spot) has `liquidation_price is None` and must
    never trigger, no matter how far price moves."""
    pos = _FakePosition(side=PositionSide.LONG, leverage=1.0, liquidation_price=None)

    triggered, still_open = policy.evaluate_liquidations([pos], high=1_000.0, low=0.01)

    assert triggered == []
    assert still_open == [pos]


def test_calculate_realized_pnl_leveraged_and_short(policy: MarginRiskPolicy):
    # Leveraged LONG (2x): margin $500, 10 qty at $100, exit at $110.
    # Price gain = (110 - 100) * 10 = $100. Entry fee $1.0, Exit fee $1.1.
    # PnL = 100 - 2.1 = $97.90. Balance release = 500 + 97.9 = $597.90.
    pnl, pnl_pct, balance_release = policy.calculate_realized_pnl(
        side=PositionSide.LONG,
        leverage=2.0,
        quantity=10.0,
        entry_price=100.0,
        exit_price=110.0,
        balance_before_entry=500.0,
        entry_fee=1.0,
        exit_fee=1.1,
    )
    assert pnl == pytest.approx(97.9)
    assert pnl_pct == pytest.approx(97.9 / 500.0 * 100.0)
    assert balance_release == pytest.approx(597.9)

    # SHORT: margin $1000, 10 qty at $100, cover at $90.
    # Gain = (100 - 90) * 10 = $100. Entry fee $1.0, Exit fee $0.9.
    # PnL = 100 - 1.9 = $98.10. Balance release = 1000 + 98.1 = $1098.10.
    pnl, pnl_pct, balance_release = policy.calculate_realized_pnl(
        side=PositionSide.SHORT,
        leverage=1.0,
        quantity=10.0,
        entry_price=100.0,
        exit_price=90.0,
        balance_before_entry=1000.0,
        entry_fee=1.0,
        exit_fee=0.9,
    )
    assert pnl == pytest.approx(98.1)
    assert pnl_pct == pytest.approx(9.81)
    assert balance_release == pytest.approx(1098.1)
