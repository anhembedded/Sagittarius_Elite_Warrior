from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.domain.trading.policies.position_sizing_bridge import (
    calculate_live_order_quantity,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_sizing import (
    PositionSizing,
    PositionSizingType,
)


def test_percent_of_equity_sizes_against_real_balance() -> None:
    """20% of a 1,000 USDT balance at 1x leverage, price 64,000, step
    0.001: 200 USDT / 64,000 = 0.003125 -> rounds down to 0.003."""
    quantity = calculate_live_order_quantity(
        sizing=PositionSizing(type=PositionSizingType.PERCENT_OF_EQUITY, value=20.0),
        available_balance=Decimal(1000),
        reference_price=Decimal(64000),
        leverage=1.0,
        step_size=Decimal("0.001"),
    )
    assert quantity == Decimal("0.003")


def test_fixed_cash_ignores_balance_beyond_availability_check() -> None:
    quantity = calculate_live_order_quantity(
        sizing=PositionSizing(type=PositionSizingType.FIXED_CASH, value=500.0),
        available_balance=Decimal(1000),
        reference_price=Decimal(500),
        leverage=1.0,
        step_size=Decimal("0.01"),
    )
    assert quantity == Decimal("1.00")


def test_zero_reference_price_returns_zero_quantity() -> None:
    quantity = calculate_live_order_quantity(
        sizing=PositionSizing(type=PositionSizingType.PERCENT_OF_EQUITY, value=20.0),
        available_balance=Decimal(1000),
        reference_price=Decimal(0),
        leverage=1.0,
        step_size=Decimal("0.001"),
    )
    assert quantity == Decimal(0)


def test_risk_percent_without_stop_loss_returns_zero_quantity() -> None:
    """`MarginRiskPolicy`'s own contract: RISK_PERCENT sizing needs a
    stop-loss distance to convert a risk % into a quantity; without one it
    returns (0, 0), and this bridge passes that through as zero rather
    than raising."""
    quantity = calculate_live_order_quantity(
        sizing=PositionSizing(type=PositionSizingType.RISK_PERCENT, value=1.0),
        available_balance=Decimal(1000),
        reference_price=Decimal(64000),
        leverage=1.0,
        step_size=Decimal("0.001"),
    )
    assert quantity == Decimal(0)
