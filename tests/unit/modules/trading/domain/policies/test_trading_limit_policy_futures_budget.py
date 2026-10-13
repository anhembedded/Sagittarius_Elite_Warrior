"""`EPIC-039D` (DECISION O2) — a Futures owner is judged in notional and margin.

@details Each ceiling is shown passing exactly at it and refused one step past
it, so flipping a `<=` turns a test red. The Spot judgement is pinned by
`test_trading_limit_policy_owner_budget.py`, which runs unmodified; the last
test here shows the same Spot facts judged the same with the new field unset."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_purpose import (
    OrderPurpose,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    EMPTY_INVENTORY,
    FuturesLimits,
    OwnerBudget,
    OwnerBudgetFacts,
    PositionExposure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    EMPTY_POSITION,
    OwnerPosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    DEFAULT_TRADING_LIMITS,
    TradingLimitContext,
    TradingLimitViolation,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.trading_limit_policy import (
    TradingLimitPolicy,
)

BUY, SELL = OrderSide.BUY, OrderSide.SELL
#: The per-order cap still applies to a budgeted order (ADR D21); this one is out of the way.
_LIMITS_OF_THE_SESSION = replace(
    DEFAULT_TRADING_LIMITS, max_notional_per_order=Decimal(1_000_000)
)
#: 100 USDT of margin at 5x: the position may be worth 500 USDT.
_LIMITS = FuturesLimits(Decimal(500), 5, Decimal(100))
_BUDGET = OwnerBudget(
    10,
    Decimal(1000),
    timedelta(milliseconds=250),
    60,
    timedelta(minutes=1),
    futures=_LIMITS,
)


def _facts(
    side: OrderSide = BUY,
    quantity: str = "1",
    *,
    held: str = "0",
    buys: str = "0",
    sells: str = "0",
    reduce_only: bool = False,
    limits: FuturesLimits = _LIMITS,
    open_price: str = "100",
    entry: str = "100",
) -> OwnerBudgetFacts:
    position = (
        EMPTY_POSITION
        if Decimal(held) == 0
        else OwnerPosition(Decimal(held), Decimal(entry), Decimal(0), Decimal(0))
    )
    return OwnerBudgetFacts(
        budget=replace(_BUDGET, futures=limits),
        open_order_count=0,
        open_buy_quote=Decimal(0),
        open_sell_quantity=Decimal(sells),
        inventory=EMPTY_INVENTORY,
        time_since_last_order=None,
        orders_in_window=0,
        order_side=side,
        order_quantity=Decimal(quantity),
        position=PositionExposure(
            position,
            Decimal(buys),
            Decimal(sells),
            Decimal(buys) * Decimal(open_price),
            Decimal(sells) * Decimal(open_price),
            order_reduce_only=reduce_only,
        ),
    )


def _violation(
    facts: OwnerBudgetFacts, price: str = "100"
) -> TradingLimitViolation | None:
    quantity = facts.order_quantity
    context = TradingLimitContext(
        orders_sent_this_session=DEFAULT_TRADING_LIMITS.max_orders_per_session,
        order_notional=quantity * Decimal(price),
        open_position_count_for_symbol=1,
        time_since_last_order_for_symbol=timedelta(0),
        purpose=OrderPurpose.ENTRY,
        client_order_tag="a3f9c1",
        owner_budget=facts,
    )
    return TradingLimitPolicy(_LIMITS_OF_THE_SESSION).first_violation(context)


def test_the_futures_budget_refuses_notional_above_capital_times_leverage() -> None:
    assert _violation(_facts(BUY, "5")) is None  # 5 × 100 = 500 = capital × leverage
    assert (
        _violation(_facts(BUY, "5.001"))
        is TradingLimitViolation.OWNER_BUDGET_POSITION_NOTIONAL
    )


def test_open_buys_and_the_held_position_count_towards_the_ceiling() -> None:
    assert _violation(_facts(BUY, "1", held="2", buys="2")) is None
    assert (
        _violation(_facts(BUY, "1", held="2", buys="2.001"))
        is TradingLimitViolation.OWNER_BUDGET_POSITION_NOTIONAL
    )


def test_a_short_is_judged_by_the_same_ceiling() -> None:
    assert _violation(_facts(SELL, "5", sells="0")) is None
    assert (
        _violation(_facts(SELL, "1", held="-2", sells="2.001"))
        is TradingLimitViolation.OWNER_BUDGET_POSITION_NOTIONAL
    )


def test_the_margin_is_a_ceiling_of_its_own() -> None:
    looser_notional = FuturesLimits(Decimal(5000), 5, Decimal(100))

    assert _violation(_facts(BUY, "5", limits=looser_notional)) is None
    assert (
        _violation(_facts(BUY, "5.001", limits=looser_notional))
        is TradingLimitViolation.OWNER_BUDGET_MARGIN
    )


def test_a_reduce_only_exit_passes_even_when_the_owner_is_over_the_ceiling() -> None:
    over = _facts(SELL, "1", held="6", reduce_only=True)
    assert _violation(over) is None


def test_a_sell_that_only_closes_passes_even_when_over_the_ceiling() -> None:
    assert _violation(_facts(SELL, "1", held="6", buys="0")) is None


def test_the_worst_case_is_the_larger_of_the_long_and_the_short_case() -> None:
    # Long 2 with 6 resting sells and one more: all fill, the owner is short 5.
    assert _violation(_facts(SELL, "1", held="2", sells="6")) is None
    assert (
        _violation(_facts(SELL, "1", held="2", sells="7"))
        is TradingLimitViolation.OWNER_BUDGET_POSITION_NOTIONAL
    )


def test_the_cheaper_the_price_the_more_the_ceiling_allows() -> None:
    assert _violation(_facts(BUY, "10"), price="50") is None
    assert (
        _violation(_facts(BUY, "10.001"), price="50")
        is TradingLimitViolation.OWNER_BUDGET_POSITION_NOTIONAL
    )


def test_the_caps_on_orders_and_spacing_apply_to_a_futures_owner_unchanged() -> None:
    full = replace(_facts(BUY, "1"), open_order_count=10)
    assert _violation(full) is TradingLimitViolation.OWNER_BUDGET_OPEN_ORDERS
    rushed = replace(_facts(BUY, "1"), time_since_last_order=timedelta(milliseconds=1))
    assert _violation(rushed) is TradingLimitViolation.OWNER_BUDGET_SPACING


def test_a_position_without_futures_limits_cannot_be_built() -> None:
    with pytest.raises(ValueError, match="Futures limits"):
        replace(_facts(), budget=replace(_BUDGET, futures=None))


def test_a_futures_budget_must_be_positive_and_leveraged() -> None:
    with pytest.raises(ValueError, match="leverage"):
        FuturesLimits(Decimal(500), 0, Decimal(100))
    with pytest.raises(ValueError, match="positive"):
        FuturesLimits(Decimal(0), 5, Decimal(100))


def test_the_spot_budget_judgement_is_unchanged() -> None:
    spot = OwnerBudgetFacts(
        budget=replace(_BUDGET, futures=None),
        open_order_count=0,
        open_buy_quote=Decimal(0),
        open_sell_quantity=Decimal(0),
        inventory=EMPTY_INVENTORY,
        time_since_last_order=None,
        orders_in_window=0,
        order_side=SELL,
        order_quantity=Decimal(1),
    )

    assert _violation(spot) is TradingLimitViolation.OWNER_BUDGET_SELL_EXCEEDS_INVENTORY


def test_the_verdict_does_not_depend_on_the_order_a_ladder_is_sent_in() -> None:
    """A ladder of BUY 1 at 100, 90 and 80 against a ceiling of 250 is refused at its
    third level whichever way it is sent (review of PR #485)."""
    ceiling = FuturesLimits(Decimal(250), 5, Decimal(50))

    def third_is_refused(prices: tuple[str, str, str]) -> bool:
        first, second, third = prices
        resting = Decimal(first) + Decimal(second)
        facts = replace(
            _facts(BUY, "1", buys="2", limits=ceiling),
            position=PositionExposure(
                EMPTY_POSITION,
                Decimal(2),
                Decimal(0),
                resting,
                Decimal(0),
                order_reduce_only=False,
            ),
        )
        return (
            _violation(facts, price=third)
            is TradingLimitViolation.OWNER_BUDGET_POSITION_NOTIONAL
        )

    assert third_is_refused(("100", "90", "80"))
    assert third_is_refused(("80", "90", "100"))
    assert not third_is_refused(("80", "70", "100"))  # 250 exactly


def test_a_held_position_is_valued_at_its_entry_not_at_the_new_orders_price() -> None:
    # Held 2 at 100 (200) plus BUY 10 at 10 (100): 300 > 250, whatever the new price.
    ceiling = FuturesLimits(Decimal(250), 5, Decimal(50))
    assert (
        _violation(_facts(BUY, "10", held="2", limits=ceiling), price="10")
        is TradingLimitViolation.OWNER_BUDGET_POSITION_NOTIONAL
    )
