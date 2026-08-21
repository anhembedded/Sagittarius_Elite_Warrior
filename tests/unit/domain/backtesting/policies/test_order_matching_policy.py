from __future__ import annotations

from dataclasses import dataclass

import pytest
from Sagittarius_Elite_Warrior.src.domain.backtesting.exit_reason import ExitReason
from Sagittarius_Elite_Warrior.src.domain.backtesting.policies.order_matching_policy import (
    OrderMatchingPolicy,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_side import (
    PositionSide,
)


@dataclass
class _FakeStoppablePosition:
    side: PositionSide
    stop_loss_price: float | None = None
    take_profit_price: float | None = None


@pytest.fixture
def policy() -> OrderMatchingPolicy:
    return OrderMatchingPolicy()


def test_slippage_delta_calculation(policy: OrderMatchingPolicy):
    # 5 ticks * 0.01 tick_size = 0.05
    assert policy.calculate_slippage_delta(5, 0.01) == pytest.approx(0.05)
    assert policy.calculate_slippage_delta(0, 0.01) == 0.0


def test_entry_and_exit_effective_price_with_slippage(policy: OrderMatchingPolicy):
    slippage = 0.5

    # LONG entry buys higher, exit sells lower
    assert (
        policy.calculate_entry_effective_price(PositionSide.LONG, 100.0, slippage)
        == 100.5
    )
    assert (
        policy.calculate_exit_effective_price(PositionSide.LONG, 100.0, slippage)
        == 99.5
    )

    # SHORT entry sells lower, exit covers higher
    assert (
        policy.calculate_entry_effective_price(PositionSide.SHORT, 100.0, slippage)
        == 99.5
    )
    assert (
        policy.calculate_exit_effective_price(PositionSide.SHORT, 100.0, slippage)
        == 100.5
    )

    # Extreme slippage clamping to 0.0
    assert policy.calculate_entry_effective_price(PositionSide.SHORT, 10.0, 15.0) == 0.0
    assert policy.calculate_exit_effective_price(PositionSide.LONG, 10.0, 15.0) == 0.0


def test_stop_loss_and_take_profit_price_calculation(policy: OrderMatchingPolicy):
    # If pct is None, returns None
    assert policy.calculate_stop_loss_price(PositionSide.LONG, 100.0, None) is None
    assert policy.calculate_take_profit_price(PositionSide.LONG, 100.0, None) is None

    # LONG: SL is 5% below (95.0), TP is 10% above (110.0)
    assert policy.calculate_stop_loss_price(
        PositionSide.LONG, 100.0, 5.0
    ) == pytest.approx(95.0)
    assert policy.calculate_take_profit_price(
        PositionSide.LONG, 100.0, 10.0
    ) == pytest.approx(110.0)

    # SHORT: SL is 5% above (105.0), TP is 10% below (90.0)
    assert policy.calculate_stop_loss_price(
        PositionSide.SHORT, 100.0, 5.0
    ) == pytest.approx(105.0)
    assert policy.calculate_take_profit_price(
        PositionSide.SHORT, 100.0, 10.0
    ) == pytest.approx(90.0)


def test_evaluate_intrabar_stops_long_single_hits(policy: OrderMatchingPolicy):
    pos = _FakeStoppablePosition(
        side=PositionSide.LONG,
        stop_loss_price=95.0,
        take_profit_price=110.0,
    )

    # Bar touches low 94.0 -> SL hit
    triggered, still_open = policy.evaluate_intrabar_stops([pos], high=105.0, low=94.0)
    assert len(triggered) == 1
    assert triggered[0] == (pos, 95.0, ExitReason.STOP_LOSS)
    assert still_open == []

    # Bar touches high 112.0 -> TP hit
    triggered, still_open = policy.evaluate_intrabar_stops([pos], high=112.0, low=98.0)
    assert len(triggered) == 1
    assert triggered[0] == (pos, 110.0, ExitReason.TAKE_PROFIT)
    assert still_open == []


def test_evaluate_intrabar_stops_short_single_hits(policy: OrderMatchingPolicy):
    pos = _FakeStoppablePosition(
        side=PositionSide.SHORT,
        stop_loss_price=105.0,
        take_profit_price=90.0,
    )

    # Bar touches high 106.0 -> SL hit
    triggered, still_open = policy.evaluate_intrabar_stops([pos], high=106.0, low=95.0)
    assert len(triggered) == 1
    assert triggered[0] == (pos, 105.0, ExitReason.STOP_LOSS)
    assert still_open == []

    # Bar touches low 89.0 -> TP hit
    triggered, still_open = policy.evaluate_intrabar_stops([pos], high=102.0, low=89.0)
    assert len(triggered) == 1
    assert triggered[0] == (pos, 90.0, ExitReason.TAKE_PROFIT)
    assert still_open == []


def test_evaluate_intrabar_stops_tie_breaker_stop_loss_wins(
    policy: OrderMatchingPolicy,
):
    # Long position where bar touches both SL (95.0) and TP (110.0)
    long_pos = _FakeStoppablePosition(
        side=PositionSide.LONG,
        stop_loss_price=95.0,
        take_profit_price=110.0,
    )
    triggered, _ = policy.evaluate_intrabar_stops([long_pos], high=115.0, low=90.0)
    assert len(triggered) == 1
    assert triggered[0][2] == ExitReason.STOP_LOSS

    # Short position where bar touches both SL (105.0) and TP (90.0)
    short_pos = _FakeStoppablePosition(
        side=PositionSide.SHORT,
        stop_loss_price=105.0,
        take_profit_price=90.0,
    )
    triggered, _ = policy.evaluate_intrabar_stops([short_pos], high=115.0, low=85.0)
    assert len(triggered) == 1
    assert triggered[0][2] == ExitReason.STOP_LOSS
