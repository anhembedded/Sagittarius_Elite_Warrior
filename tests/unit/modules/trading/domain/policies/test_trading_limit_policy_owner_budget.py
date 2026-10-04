"""`EPIC-029` ADR D6 — a tagged order is judged by its owner's budget.

@details Each of the five checks is shown passing at its ceiling and
refused one step past it (boundary value analysis), so flipping a `<=`
into a `<`, or dropping the `+ 1` that counts the order being sent, turns a
test red. The signal limits' own file (`test_trading_limit_policy.py`) runs
unmodified: an untagged order never reaches this branch.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_purpose import (
    OrderPurpose,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudget,
    OwnerBudgetFacts,
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    DEFAULT_TRADING_LIMITS,
    TradingLimitContext,
    TradingLimitViolation,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.trading_limit_policy import (
    TradingLimitPolicy,
)

_BUDGET = OwnerBudget(
    max_open_orders=10,
    max_exposure_quote=Decimal(1000),
    min_order_spacing=timedelta(milliseconds=250),
    max_orders_per_window=60,
    window=timedelta(minutes=1),
)
_FACTS = OwnerBudgetFacts(
    budget=_BUDGET,
    open_order_count=0,
    open_buy_quote=Decimal(0),
    open_sell_quantity=Decimal(0),
    inventory=OwnerInventory(Decimal(0), Decimal(0)),
    time_since_last_order=None,
    orders_in_window=0,
    order_side=OrderSide.BUY,
    order_quantity=Decimal("0.001"),
)


def _violation(
    facts: OwnerBudgetFacts | None = _FACTS,
    notional: Decimal = Decimal(100),
    purpose: OrderPurpose = OrderPurpose.ENTRY,
) -> TradingLimitViolation | None:
    context = TradingLimitContext(
        # Every signal limit would refuse this order: a budgeted owner's
        # order must not be judged by them.
        orders_sent_this_session=DEFAULT_TRADING_LIMITS.max_orders_per_session,
        order_notional=notional,
        open_position_count_for_symbol=1,
        time_since_last_order_for_symbol=timedelta(0),
        purpose=purpose,
        client_order_tag="a3f9c1",
        owner_budget=facts,
    )
    return TradingLimitPolicy(DEFAULT_TRADING_LIMITS).first_violation(context)


def test_the_signal_limits_do_not_judge_a_budgeted_order() -> None:
    assert _violation() is None


class TestOpenOrders:
    def test_the_tenth_order_passes(self) -> None:
        assert _violation(replace(_FACTS, open_order_count=9)) is None

    def test_the_eleventh_order_is_refused(self) -> None:
        assert (
            _violation(replace(_FACTS, open_order_count=10))
            is TradingLimitViolation.OWNER_BUDGET_OPEN_ORDERS
        )


class TestExposure:
    def test_a_buy_reaching_the_ceiling_passes(self) -> None:
        facts = replace(
            _FACTS,
            open_buy_quote=Decimal(500),
            inventory=OwnerInventory(Decimal("0.01"), Decimal(400)),
        )
        assert _violation(facts, notional=Decimal(100)) is None

    def test_a_buy_past_the_ceiling_is_refused(self) -> None:
        facts = replace(
            _FACTS,
            open_buy_quote=Decimal(500),
            inventory=OwnerInventory(Decimal("0.01"), Decimal(400)),
        )
        assert (
            _violation(facts, notional=Decimal("100.01"))
            is TradingLimitViolation.OWNER_BUDGET_EXPOSURE
        )

    def test_a_sell_never_counts_as_exposure(self) -> None:
        facts = replace(
            _FACTS,
            open_buy_quote=Decimal(1000),
            inventory=OwnerInventory(Decimal("0.01"), Decimal(400)),
            order_side=OrderSide.SELL,
            order_quantity=Decimal("0.01"),
        )
        assert _violation(facts) is None


class TestSellWithinInventory:
    def test_selling_the_whole_inventory_passes(self) -> None:
        facts = replace(
            _FACTS,
            inventory=OwnerInventory(Decimal("0.01"), Decimal(600)),
            open_sell_quantity=Decimal("0.004"),
            order_side=OrderSide.SELL,
            order_quantity=Decimal("0.006"),
        )
        assert _violation(facts) is None

    def test_selling_past_the_inventory_is_refused(self) -> None:
        facts = replace(
            _FACTS,
            inventory=OwnerInventory(Decimal("0.01"), Decimal(600)),
            open_sell_quantity=Decimal("0.004"),
            order_side=OrderSide.SELL,
            order_quantity=Decimal("0.00601"),
        )
        assert (
            _violation(facts)
            is TradingLimitViolation.OWNER_BUDGET_SELL_EXCEEDS_INVENTORY
        )

    def test_a_close_purpose_does_not_exempt_a_sell(self) -> None:
        """Spot has no reduce-only: the budget branch runs before the
        `only_reduces` return (ADR D6 r2)."""
        facts = replace(
            _FACTS, order_side=OrderSide.SELL, order_quantity=Decimal("0.001")
        )
        assert (
            _violation(facts, purpose=OrderPurpose.CLOSE)
            is TradingLimitViolation.OWNER_BUDGET_SELL_EXCEEDS_INVENTORY
        )


class TestSpacing:
    def test_exactly_the_spacing_passes(self) -> None:
        facts = replace(_FACTS, time_since_last_order=timedelta(milliseconds=250))
        assert _violation(facts) is None

    def test_one_millisecond_short_is_refused(self) -> None:
        facts = replace(_FACTS, time_since_last_order=timedelta(milliseconds=249))
        assert _violation(facts) is TradingLimitViolation.OWNER_BUDGET_SPACING


class TestRate:
    def test_the_last_order_of_the_window_passes(self) -> None:
        assert _violation(replace(_FACTS, orders_in_window=59)) is None

    def test_one_past_the_window_is_refused(self) -> None:
        assert (
            _violation(replace(_FACTS, orders_in_window=60))
            is TradingLimitViolation.OWNER_BUDGET_RATE
        )


def test_the_per_order_notional_cap_still_refuses_a_budgeted_order() -> None:
    """ADR D21: bots slice their market orders under the cap."""
    cap = DEFAULT_TRADING_LIMITS.max_notional_per_order
    assert _violation(notional=cap) is None
    assert (
        _violation(notional=cap + Decimal("0.01"))
        is TradingLimitViolation.MAX_NOTIONAL_PER_ORDER
    )


def test_a_tagged_order_without_a_budget_is_refused() -> None:
    assert _violation(facts=None) is TradingLimitViolation.OWNER_BUDGET_MISSING


def test_a_tagged_order_without_a_budget_is_refused_whatever_its_purpose() -> None:
    assert (
        _violation(facts=None, purpose=OrderPurpose.CLOSE)
        is TradingLimitViolation.OWNER_BUDGET_MISSING
    )
