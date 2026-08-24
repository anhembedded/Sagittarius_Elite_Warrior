from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.domain.backtesting.policies.fee_calculator_policy import (
    FeeCalculatorPolicy,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.commission_type import (
    CommissionType,
)


@pytest.fixture
def policy() -> FeeCalculatorPolicy:
    return FeeCalculatorPolicy()


def test_percent_commission_entry_and_exit(policy: FeeCalculatorPolicy):
    # $1,000 notional at price $100 with 0.1% fee
    # entry_fee = 1000 * 0.001 = 1.0
    # net_notional = 999.0 -> quantity = 999.0 / 100 = 9.99
    entry_fee, qty = policy.calculate_entry_fee_and_quantity(
        notional_capital=1000.0,
        effective_price=100.0,
        commission_type=CommissionType.PERCENT,
        commission_value=0.1,
    )
    assert entry_fee == pytest.approx(1.0)
    assert qty == pytest.approx(9.99)

    # exit fee on 9.99 qty at $120 (notional $1198.8) with 0.1% fee = 1.1988
    exit_fee = policy.calculate_exit_fee(
        quantity=qty,
        exit_price=120.0,
        commission_type=CommissionType.PERCENT,
        commission_value=0.1,
    )
    assert exit_fee == pytest.approx(1.1988)


def test_cash_per_order_commission(policy: FeeCalculatorPolicy):
    # $1,000 notional at $100 with $2.5 fixed fee per order
    # The fixed entry fee is 2.5, leaving 997.5 notional and 9.975 quantity.
    entry_fee, qty = policy.calculate_entry_fee_and_quantity(
        notional_capital=1000.0,
        effective_price=100.0,
        commission_type=CommissionType.CASH_PER_ORDER,
        commission_value=2.5,
    )
    assert entry_fee == 2.5
    assert qty == pytest.approx(9.975)

    exit_fee = policy.calculate_exit_fee(
        quantity=qty,
        exit_price=150.0,
        commission_type=CommissionType.CASH_PER_ORDER,
        commission_value=2.5,
    )
    assert exit_fee == 2.5


def test_cash_per_contract_commission(policy: FeeCalculatorPolicy):
    # $1,000 notional at $100 with $0.05 fee per contract
    # Quantity is 1000 / 100.05; entry fee is quantity multiplied by 0.05.
    entry_fee, qty = policy.calculate_entry_fee_and_quantity(
        notional_capital=1000.0,
        effective_price=100.0,
        commission_type=CommissionType.CASH_PER_CONTRACT,
        commission_value=0.05,
    )
    assert qty == pytest.approx(1000.0 / 100.05)
    assert entry_fee == pytest.approx(qty * 0.05)

    exit_fee = policy.calculate_exit_fee(
        quantity=qty,
        exit_price=110.0,
        commission_type=CommissionType.CASH_PER_CONTRACT,
        commission_value=0.05,
    )
    assert exit_fee == pytest.approx(qty * 0.05)


def test_zero_or_negative_inputs_return_zero(policy: FeeCalculatorPolicy):
    assert policy.calculate_entry_fee_and_quantity(
        0.0, 100.0, CommissionType.PERCENT, 0.1
    ) == (0.0, 0.0)
    assert policy.calculate_entry_fee_and_quantity(
        1000.0, 0.0, CommissionType.PERCENT, 0.1
    ) == (0.0, 0.0)
    assert policy.calculate_entry_fee_and_quantity(
        -100.0, 100.0, CommissionType.PERCENT, 0.1
    ) == (0.0, 0.0)
    assert policy.calculate_exit_fee(0.0, 100.0, CommissionType.PERCENT, 0.1) == 0.0
    assert policy.calculate_exit_fee(10.0, 0.0, CommissionType.PERCENT, 0.1) == 0.0


def test_excessive_fee_exceeding_notional_returns_zero(policy: FeeCalculatorPolicy):
    # $10 fee on $5 notional
    entry_fee, qty = policy.calculate_entry_fee_and_quantity(
        notional_capital=5.0,
        effective_price=100.0,
        commission_type=CommissionType.CASH_PER_ORDER,
        commission_value=10.0,
    )
    assert entry_fee == 0.0
    assert qty == 0.0
