from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.domain.backtesting.policies.margin_risk_policy import (
    MarginRiskPolicy,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_sizing import (
    PositionSizing,
    PositionSizingType,
)


@pytest.fixture
def policy() -> MarginRiskPolicy:
    return MarginRiskPolicy()


def test_get_leverage(policy: MarginRiskPolicy):
    assert policy.get_leverage(PositionSide.LONG, 3.0, 5.0) == 3.0
    assert policy.get_leverage(PositionSide.SHORT, 3.0, 5.0) == 5.0


def test_calculate_margin_and_notional_percent_of_equity(policy: MarginRiskPolicy):
    sizing = PositionSizing(PositionSizingType.PERCENT_OF_EQUITY, 50.0)
    # $10,000 equity, available balance $10,000, 3x leverage -> margin = $5,000, notional = $15,000
    margin, notional = policy.calculate_margin_and_notional(
        side=PositionSide.LONG,
        effective_price=100.0,
        current_equity=10000.0,
        available_balance=10000.0,
        sizing=sizing,
        leverage=3.0,
    )
    assert margin == 5000.0
    assert notional == 15000.0


def test_calculate_margin_and_notional_fixed_cash(policy: MarginRiskPolicy):
    sizing = PositionSizing(PositionSizingType.FIXED_CASH, 2000.0)
    # $2,000 cash with 2x leverage -> margin = $2,000, notional = $4,000
    margin, notional = policy.calculate_margin_and_notional(
        side=PositionSide.LONG,
        effective_price=100.0,
        current_equity=10000.0,
        available_balance=5000.0,
        sizing=sizing,
        leverage=2.0,
    )
    assert margin == 2000.0
    assert notional == 4000.0


def test_calculate_margin_and_notional_fixed_contracts(policy: MarginRiskPolicy):
    sizing = PositionSizing(PositionSizingType.FIXED_CONTRACTS, 10.0)
    # 10 contracts at $100 = $1,000 notional. At 5x leverage -> margin = $200
    margin, notional = policy.calculate_margin_and_notional(
        side=PositionSide.LONG,
        effective_price=100.0,
        current_equity=10000.0,
        available_balance=5000.0,
        sizing=sizing,
        leverage=5.0,
    )
    assert margin == 200.0
    assert notional == 1000.0


def test_calculate_margin_and_notional_risk_percent(policy: MarginRiskPolicy):
    sizing = PositionSizing(PositionSizingType.RISK_PERCENT, 2.0)
    # Missing stop loss pct returns (0.0, 0.0)
    assert policy.calculate_margin_and_notional(
        side=PositionSide.LONG,
        effective_price=100.0,
        current_equity=10000.0,
        available_balance=10000.0,
        sizing=sizing,
        leverage=2.0,
        stop_loss_pct=None,
    ) == (0.0, 0.0)

    # 2% risk on $10,000 equity = $200 risk amount.
    # 5% stop distance -> notional = 200 * (100 / 5) = $4,000.
    # At 2x leverage -> margin = $2,000.
    margin, notional = policy.calculate_margin_and_notional(
        side=PositionSide.LONG,
        effective_price=100.0,
        current_equity=10000.0,
        available_balance=10000.0,
        sizing=sizing,
        leverage=2.0,
        stop_loss_pct=5.0,
    )
    assert margin == pytest.approx(2000.0)
    assert notional == pytest.approx(4000.0)


def test_calculate_margin_clamped_to_available_balance(policy: MarginRiskPolicy):
    sizing = PositionSizing(PositionSizingType.FIXED_CASH, 5000.0)
    # Wants $5,000 margin with 2x leverage ($10,000 notional), but only $2,500 available
    # Clamps margin to $2,500 and scales notional to $5,000 (maintaining 2x ratio)
    margin, notional = policy.calculate_margin_and_notional(
        side=PositionSide.LONG,
        effective_price=100.0,
        current_equity=10000.0,
        available_balance=2500.0,
        sizing=sizing,
        leverage=2.0,
    )
    assert margin == 2500.0
    assert notional == 5000.0


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
