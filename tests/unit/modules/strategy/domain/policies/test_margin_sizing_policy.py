"""`MarginSizingPolicy` — the five sizing cases, moved with the rule.

`EPIC-025` PR 2.1d (ADR D17) moved
`MarginRiskPolicy.calculate_margin_and_notional()` into `modules/strategy` as
`ISizingPolicy`'s one implementation. These cases came with it from
`tests/unit/domain/backtesting/policies/test_margin_risk_policy.py`, numbers
and comments unchanged — they are the arithmetic of `BOT-104` and `BOT-041`,
and a moved rule that computed something different would be a behaviour change
ADR D12 does not allow. What changed is the shape of the answer: a named
`MarginAllocation` instead of a bare `tuple[float, float]`, because a published
contract may not return an unnamed pair (`architecture-rule.md` §2.1).

The *guarantees* those numbers stand for — the clamp, the leverage ratio
surviving it, "never raises" — live in `SizingPolicyContract` and are checked
against this same implementation by
`tests/unit/modules/strategy/contracts/test_sizing_policy_contract.py`. These
cases stay because a suite written for whoever implements the port next is a
different thing from the table of what today's formula computes.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.position_sizing import (
    PositionSizing,
    PositionSizingType,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.policies.margin_sizing_policy import (
    MarginSizingPolicy,
)


@pytest.fixture
def policy() -> MarginSizingPolicy:
    return MarginSizingPolicy()


def test_percent_of_equity(policy: MarginSizingPolicy) -> None:
    sizing = PositionSizing(PositionSizingType.PERCENT_OF_EQUITY, 50.0)
    # $10,000 equity, available balance $10,000, 3x leverage -> margin = $5,000, notional = $15,000
    allocation = policy.allocate(
        sizing=sizing,
        effective_price=100.0,
        current_equity=10000.0,
        available_balance=10000.0,
        leverage=3.0,
    )
    assert allocation.margin == 5000.0
    assert allocation.notional_capital == 15000.0


def test_fixed_cash(policy: MarginSizingPolicy) -> None:
    sizing = PositionSizing(PositionSizingType.FIXED_CASH, 2000.0)
    # $2,000 cash with 2x leverage -> margin = $2,000, notional = $4,000
    allocation = policy.allocate(
        sizing=sizing,
        effective_price=100.0,
        current_equity=10000.0,
        available_balance=5000.0,
        leverage=2.0,
    )
    assert allocation.margin == 2000.0
    assert allocation.notional_capital == 4000.0


def test_fixed_contracts(policy: MarginSizingPolicy) -> None:
    sizing = PositionSizing(PositionSizingType.FIXED_CONTRACTS, 10.0)
    # 10 contracts at $100 = $1,000 notional. At 5x leverage -> margin = $200
    allocation = policy.allocate(
        sizing=sizing,
        effective_price=100.0,
        current_equity=10000.0,
        available_balance=5000.0,
        leverage=5.0,
    )
    assert allocation.margin == 200.0
    assert allocation.notional_capital == 1000.0


def test_risk_percent(policy: MarginSizingPolicy) -> None:
    sizing = PositionSizing(PositionSizingType.RISK_PERCENT, 2.0)
    # Missing stop loss pct is not fundable
    assert (
        policy.allocate(
            sizing=sizing,
            effective_price=100.0,
            current_equity=10000.0,
            available_balance=10000.0,
            leverage=2.0,
            stop_loss_pct=None,
        ).is_fundable
        is False
    )

    # 2% risk on $10,000 equity = $200 risk amount.
    # 5% stop distance -> notional = 200 * (100 / 5) = $4,000.
    # At 2x leverage -> margin = $2,000.
    allocation = policy.allocate(
        sizing=sizing,
        effective_price=100.0,
        current_equity=10000.0,
        available_balance=10000.0,
        leverage=2.0,
        stop_loss_pct=5.0,
    )
    assert allocation.margin == pytest.approx(2000.0)
    assert allocation.notional_capital == pytest.approx(4000.0)


def test_margin_clamped_to_available_balance(policy: MarginSizingPolicy) -> None:
    sizing = PositionSizing(PositionSizingType.FIXED_CASH, 5000.0)
    # Wants $5,000 margin with 2x leverage ($10,000 notional), but only $2,500 available
    # Clamps margin to $2,500 and scales notional to $5,000 (maintaining 2x ratio)
    allocation = policy.allocate(
        sizing=sizing,
        effective_price=100.0,
        current_equity=10000.0,
        available_balance=2500.0,
        leverage=2.0,
    )
    assert allocation.margin == 2500.0
    assert allocation.notional_capital == 5000.0
