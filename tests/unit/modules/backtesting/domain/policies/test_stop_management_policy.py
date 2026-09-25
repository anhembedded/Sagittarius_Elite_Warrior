"""Direct, isolated unit tests for `StopManagementPolicy` (`BOT-105A`,
extracted from `PaperExchange` in `PR #266`'s follow-up to keep that file
under the 400-line ceiling). The exhaustive behavioral matrix (LONG/SHORT,
same-bar triggers, coordination with a static `stop_loss_pct`, mutation
verification) already lives in `test_paper_exchange.py`'s own BOT-105A
blocks, exercised through the real `PaperExchange`/`check_intrabar_stops()`
composition; these tests instead prove the policy works standalone, against
real `OpenPosition`/`FillPricing` collaborators, with no `PaperExchange` in
the loop at all."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.position_sizing import (
    PositionSizing,
    PositionSizingType,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.broker_simulation_config import (
    BrokerSimulationConfig,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.fill_pricing import (
    FillPricing,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.open_position import (
    OpenPosition,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.policies.stop_management_policy import (
    StopManagementPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)

_T1 = datetime(2024, 1, 1, tzinfo=UTC)


def _position(
    side: PositionSide = PositionSide.LONG, entry_price: float = 100.0
) -> OpenPosition:
    return OpenPosition(
        quantity=10.0,
        entry_price=entry_price,
        entry_time=_T1,
        balance_before_entry=1_000.0,
        entry_fee=0.0,
        entry_reason="test",
        side=side,
    )


@pytest.fixture
def policy() -> StopManagementPolicy:
    return StopManagementPolicy()


@pytest.fixture
def pricing() -> FillPricing:
    return FillPricing(
        BrokerSimulationConfig(commission_value=0.0),
        PositionSizing(type=PositionSizingType.PERCENT_OF_EQUITY, value=100.0),
    )


def test_update_excursion_tracking_widens_mae_mfe_for_a_long_position(
    policy: StopManagementPolicy, pricing: FillPricing
):
    pos = _position(side=PositionSide.LONG)

    policy.update_excursion_tracking([pos], pricing, high=110.0, low=90.0)

    assert pos.mae_percent == pytest.approx(-10.0)  # low=90 -> value=900 (-10%)
    assert pos.mfe_percent == pytest.approx(10.0)  # high=110 -> value=1100 (+10%)


def test_update_excursion_tracking_widens_mae_mfe_for_a_short_position(
    policy: StopManagementPolicy, pricing: FillPricing
):
    pos = _position(side=PositionSide.SHORT)

    policy.update_excursion_tracking([pos], pricing, high=110.0, low=90.0)

    # A short profits as price falls: low=90 is the best price, high=110 the worst.
    assert pos.mae_percent == pytest.approx(-10.0)
    assert pos.mfe_percent == pytest.approx(10.0)


def test_apply_break_even_stops_is_a_no_op_when_trigger_is_none(
    policy: StopManagementPolicy,
):
    pos = _position()
    pos.mfe_percent = 50.0

    policy.apply_break_even_stops([pos], trigger_pct=None)

    assert pos.break_even_armed is False
    assert pos.stop_loss_price is None


def test_apply_break_even_stops_moves_stop_to_entry_exactly_once(
    policy: StopManagementPolicy,
):
    pos = _position(entry_price=100.0)
    pos.mfe_percent = 3.0

    policy.apply_break_even_stops([pos], trigger_pct=2.0)
    assert pos.break_even_armed is True
    assert pos.stop_loss_price == pytest.approx(100.0)

    # A further rally must not touch it again (one-time move).
    pos.mfe_percent = 20.0
    policy.apply_break_even_stops([pos], trigger_pct=2.0)
    assert pos.stop_loss_price == pytest.approx(100.0)


def test_apply_trailing_stops_is_a_no_op_when_either_field_is_none(
    policy: StopManagementPolicy,
):
    pos = _position()
    pos.mfe_percent = 50.0

    policy.apply_trailing_stops(
        [pos], activation_pct=None, offset_pct=5.0, high=110.0, low=108.0
    )
    assert pos.trailing_armed is False

    policy.apply_trailing_stops(
        [pos], activation_pct=2.0, offset_pct=None, high=110.0, low=108.0
    )
    assert pos.trailing_armed is False


def test_apply_trailing_stops_arms_ratchets_and_never_retreats(
    policy: StopManagementPolicy,
):
    pos = _position(side=PositionSide.LONG)
    pos.mfe_percent = 3.0

    policy.apply_trailing_stops(
        [pos], activation_pct=2.0, offset_pct=5.0, high=103.0, low=101.0
    )
    assert pos.trailing_armed is True
    assert pos.stop_loss_price == pytest.approx(103.0 * 0.95)

    # A new high ratchets the stop further up.
    policy.apply_trailing_stops(
        [pos], activation_pct=2.0, offset_pct=5.0, high=110.0, low=108.0
    )
    assert pos.stop_loss_price == pytest.approx(110.0 * 0.95)

    # No new high — the stop must not retreat even on a deep pullback.
    policy.apply_trailing_stops(
        [pos], activation_pct=2.0, offset_pct=5.0, high=105.0, low=104.0
    )
    assert pos.stop_loss_price == pytest.approx(110.0 * 0.95)
