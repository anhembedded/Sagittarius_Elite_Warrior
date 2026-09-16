"""`MarginRiskPolicy` — leverage, mark-to-market and PnL realization.

The five sizing cases that used to open this file left with the rule they
tested: `EPIC-025` PR 2.1d (ADR D17) moved
`calculate_margin_and_notional()` into `modules/strategy` as `ISizingPolicy`,
and they are now
`tests/unit/modules/strategy/domain/policies/test_margin_sizing_policy.py`
with their numbers unchanged. Nothing was dropped.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.domain.backtesting.policies.margin_risk_policy import (
    MarginRiskPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)


@pytest.fixture
def policy() -> MarginRiskPolicy:
    return MarginRiskPolicy()


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
