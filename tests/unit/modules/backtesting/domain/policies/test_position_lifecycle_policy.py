"""Direct, isolated unit tests for `PositionLifecyclePolicy` (`BOT-144`,
extracted from `PaperExchange` to keep that file under the 400-line
ceiling — the last extraction target `PR #266`'s `StopManagementPolicy`
split left behind).

The exhaustive behavioral matrix (pyramiding, slippage, commission models,
liquidation, partial take-profit) already lives in `test_paper_exchange.py`,
exercised through the real `PaperExchange`/`fill()`/`check_intrabar_stops()`
composition; these tests instead prove the policy works standalone, against
real `OpenPosition`/`FillPricing` collaborators, with no `PaperExchange` in
the loop at all — the same shape `test_stop_management_policy.py` already
uses for its own sibling policy.
"""

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
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exit_reason import (
    ExitReason,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.fill_pricing import (
    FillPricing,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.open_position import (
    OpenPosition,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.policies.position_lifecycle_policy import (
    PositionLifecyclePolicy,
    PositionOpenRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)

_T1 = datetime(2024, 1, 1, tzinfo=UTC)
_T2 = datetime(2024, 1, 2, tzinfo=UTC)
_SYMBOL = "BTCUSDT"


def _position(
    *,
    side: PositionSide = PositionSide.LONG,
    quantity: float = 10.0,
    entry_price: float = 100.0,
    balance_before_entry: float = 1_000.0,
    entry_fee: float = 0.0,
    leverage: float = 1.0,
    partial_take_profit_prices: tuple[float, ...] = (),
    partial_take_profit_close_quantities: tuple[float, ...] = (),
) -> OpenPosition:
    return OpenPosition(
        quantity=quantity,
        entry_price=entry_price,
        entry_time=_T1,
        balance_before_entry=balance_before_entry,
        entry_fee=entry_fee,
        entry_reason="test",
        side=side,
        leverage=leverage,
        partial_take_profit_prices=partial_take_profit_prices,
        partial_take_profit_close_quantities=partial_take_profit_close_quantities,
    )


def _pricing(
    sizing: PositionSizing | None = None,
    broker_cfg: BrokerSimulationConfig | None = None,
) -> FillPricing:
    return FillPricing(
        broker_cfg or BrokerSimulationConfig(commission_value=0.0),
        sizing
        or PositionSizing(type=PositionSizingType.PERCENT_OF_EQUITY, value=100.0),
    )


@pytest.fixture
def pricing() -> FillPricing:
    return _pricing()


@pytest.fixture
def policy(pricing: FillPricing) -> PositionLifecyclePolicy:
    return PositionLifecyclePolicy(
        _SYMBOL, pricing, BrokerSimulationConfig(commission_value=0.0)
    )


def _open_request(
    side: PositionSide = PositionSide.LONG, price: float = 100.0
) -> PositionOpenRequest:
    return PositionOpenRequest(
        side=side, price=price, time=_T1, reason="test", metadata={}
    )


# ---------------------------------------------------------------------------
# open_position
# ---------------------------------------------------------------------------


def test_open_position_appends_the_new_entry_and_deducts_capital():
    sizing = PositionSizing(type=PositionSizingType.FIXED_CASH, value=2_000.0)
    broker_cfg = BrokerSimulationConfig(commission_value=0.0)
    policy = PositionLifecyclePolicy(_SYMBOL, _pricing(sizing, broker_cfg), broker_cfg)

    new_positions, new_balance = policy.open_position(
        [], 10_000.0, _open_request(price=100.0)
    )

    assert len(new_positions) == 1
    assert new_positions[0].quantity == pytest.approx(20.0)  # 2000 / 100
    assert new_positions[0].entry_price == pytest.approx(100.0)
    assert new_balance == pytest.approx(8_000.0)  # 10000 - 2000


def test_open_position_rejects_an_opposite_side_while_one_is_still_open():
    """`BOT-050` — the strategy must close the opposite side explicitly
    first; this policy never implicitly reverses a position."""
    sizing = PositionSizing(type=PositionSizingType.FIXED_CASH, value=2_000.0)
    broker_cfg = BrokerSimulationConfig(commission_value=0.0, pyramiding=5)
    policy = PositionLifecyclePolicy(_SYMBOL, _pricing(sizing, broker_cfg), broker_cfg)
    existing = _position(side=PositionSide.LONG)

    new_positions, new_balance = policy.open_position(
        [existing], 10_000.0, _open_request(side=PositionSide.SHORT, price=100.0)
    )

    assert new_positions == [existing]
    assert new_balance == pytest.approx(10_000.0)


def test_open_position_rejects_beyond_the_pyramiding_limit():
    sizing = PositionSizing(type=PositionSizingType.FIXED_CASH, value=2_000.0)
    broker_cfg = BrokerSimulationConfig(commission_value=0.0, pyramiding=1)
    policy = PositionLifecyclePolicy(_SYMBOL, _pricing(sizing, broker_cfg), broker_cfg)
    existing = _position(side=PositionSide.LONG)

    new_positions, new_balance = policy.open_position(
        [existing], 10_000.0, _open_request(side=PositionSide.LONG, price=100.0)
    )

    assert new_positions == [existing]
    assert new_balance == pytest.approx(10_000.0)


def test_open_position_rejects_when_balance_cannot_fund_the_entry(
    policy: PositionLifecyclePolicy,
):
    new_positions, new_balance = policy.open_position(
        [], 0.0, _open_request(price=100.0)
    )

    assert new_positions == []
    assert new_balance == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# close_one_position
# ---------------------------------------------------------------------------


def test_close_one_position_realizes_pnl_and_releases_balance(
    policy: PositionLifecyclePolicy,
):
    pos = _position(
        quantity=20.0, entry_price=100.0, balance_before_entry=2_000.0, leverage=1.0
    )

    trade, balance_release = policy.close_one_position(
        pos, exit_price=150.0, time=_T2, exit_reason=ExitReason.STRATEGY_SIGNAL
    )

    assert trade.pnl == pytest.approx(1_000.0)  # 20 * 150 - 2000
    assert trade.quantity == pytest.approx(20.0)
    assert trade.exit_reason is ExitReason.STRATEGY_SIGNAL
    assert balance_release == pytest.approx(3_000.0)  # 2000 (margin) + 1000 (pnl)


def test_close_one_position_clamps_a_liquidation_but_not_a_regular_exit(
    policy: PositionLifecyclePolicy,
):
    """Mutation check on the `if exit_reason is ExitReason.LIQUIDATION` gate:
    the exact same catastrophic loss must be capped at the position's own
    margin only when the exit reason is actually `LIQUIDATION`
    (`clamp_liquidation_settlement`'s own contract) — proving both that the
    clamp fires and that it does not fire unconditionally."""
    leveraged = _position(
        quantity=10.0,
        entry_price=100.0,
        balance_before_entry=200.0,
        leverage=5.0,
    )

    trade, balance_release = policy.close_one_position(
        leveraged, exit_price=50.0, time=_T2, exit_reason=ExitReason.LIQUIDATION
    )

    # Uncapped this would be pnl=-500, balance_release=-300 (driving cash
    # negative) — clamped to exactly the margin lost, never more.
    assert trade.pnl == pytest.approx(-200.0)
    assert trade.pnl_percent == pytest.approx(-100.0)
    assert balance_release == pytest.approx(0.0)

    same_shape_not_liquidated = _position(
        quantity=10.0,
        entry_price=100.0,
        balance_before_entry=200.0,
        leverage=5.0,
    )

    trade2, balance_release2 = policy.close_one_position(
        same_shape_not_liquidated,
        exit_price=50.0,
        time=_T2,
        exit_reason=ExitReason.STOP_LOSS,
    )

    assert trade2.pnl == pytest.approx(-500.0)
    assert balance_release2 == pytest.approx(-300.0)


# ---------------------------------------------------------------------------
# close_partial_position
# ---------------------------------------------------------------------------


def test_close_partial_position_prorates_and_shrinks_the_position_in_place(
    policy: PositionLifecyclePolicy,
):
    pos = _position(
        quantity=100.0,
        entry_price=10.0,
        balance_before_entry=500.0,
        entry_fee=20.0,
        leverage=2.0,
    )

    trade, balance_release = policy.close_partial_position(
        pos, exit_price=15.0, time=_T2, close_qty=40.0
    )

    assert trade.quantity == pytest.approx(40.0)
    assert trade.exit_reason is ExitReason.PARTIAL_TAKE_PROFIT
    assert trade.pnl == pytest.approx(192.0)  # (15-10)*40 - prorated fee 8
    assert trade.fees_paid == pytest.approx(8.0)  # prorated entry fee only, no exit fee
    assert balance_release == pytest.approx(392.0)  # prorated margin 200 + pnl 192

    # The position itself shrinks by exactly the fraction closed (40%).
    assert pos.quantity == pytest.approx(60.0)
    assert pos.balance_before_entry == pytest.approx(300.0)
    assert pos.entry_fee == pytest.approx(12.0)


# ---------------------------------------------------------------------------
# apply_partial_take_profits
# ---------------------------------------------------------------------------


def test_apply_partial_take_profits_is_a_no_op_on_an_empty_ledger(
    policy: PositionLifecyclePolicy,
):
    trades, total_release, still_open = policy.apply_partial_take_profits(
        [], high=200.0, low=50.0, time=_T2
    )

    assert trades == []
    assert total_release == pytest.approx(0.0)
    assert still_open == []


def test_apply_partial_take_profits_ignores_a_bar_that_never_reaches_the_level(
    policy: PositionLifecyclePolicy,
):
    pos = _position(
        quantity=100.0,
        entry_price=100.0,
        balance_before_entry=10_000.0,
        partial_take_profit_prices=(110.0, 120.0),
        partial_take_profit_close_quantities=(40.0, 60.0),
    )

    trades, _total_release, still_open = policy.apply_partial_take_profits(
        [pos], high=105.0, low=100.0, time=_T2
    )

    assert trades == []
    assert pos.quantity == pytest.approx(100.0)
    assert pos.partial_tp_next_level_index == 0
    assert still_open == [pos]


def test_apply_partial_take_profits_closes_one_hit_level_and_advances_the_index(
    policy: PositionLifecyclePolicy,
):
    pos = _position(
        quantity=100.0,
        entry_price=100.0,
        balance_before_entry=10_000.0,
        partial_take_profit_prices=(110.0, 120.0),
        partial_take_profit_close_quantities=(40.0, 60.0),
    )

    trades, total_release, still_open = policy.apply_partial_take_profits(
        [pos], high=115.0, low=105.0, time=_T2
    )

    assert len(trades) == 1
    assert trades[0].quantity == pytest.approx(40.0)
    assert total_release > 0.0
    assert pos.quantity == pytest.approx(60.0)  # 100 - 40
    assert pos.partial_tp_next_level_index == 1  # advanced past the hit level
    assert still_open == [pos]  # not fully closed yet


def test_apply_partial_take_profits_drops_a_position_fully_closed_by_its_last_level(
    policy: PositionLifecyclePolicy,
):
    pos = _position(
        quantity=60.0,  # what remains after the first level already fired
        entry_price=100.0,
        balance_before_entry=6_000.0,
        partial_take_profit_prices=(110.0, 120.0),
        partial_take_profit_close_quantities=(40.0, 60.0),
    )
    pos.partial_tp_next_level_index = 1

    trades, _total_release, still_open = policy.apply_partial_take_profits(
        [pos], high=125.0, low=118.0, time=_T2
    )

    assert len(trades) == 1
    assert trades[0].quantity == pytest.approx(60.0)
    assert pos.quantity == pytest.approx(0.0)
    assert still_open == []  # identity-based removal, fully closed
