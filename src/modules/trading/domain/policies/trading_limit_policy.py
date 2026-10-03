"""`EPIC-021G` — the domain policy that decides whether a live order may be
sent at all, independent of whether the order itself is well-formed.

@details A business decision, not a coordinator's `if`: it must be
testable with zero network (`testing-rule.md` §1), and it is the one
mechanism in this epic that stops a bad signal loop from firing hundreds
of orders (§1's stated real risk). All four limits are on by default —
there is no "disable this one limit" toggle; only their numeric
thresholds are configurable (`ConfigKeys` §`TRADING_MAX_*`).

`EPIC-025` PR 2.1g moved the four value types this reads and answers with —
`TradingLimitViolation`, `TradingLimits`, `TradingLimitContext`,
`TradingLimitCheck` — into `contracts/trading_limits.py`, because
`ExecuteOrderResult` had been publishing all of them since PR 1.3b while their
file stayed internal. What is left here is the **judgement**, which no consumer
outside this module may reach: publishing the answer is not publishing the
decision.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetFacts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    SIGNAL_LIMITS,
    TradingLimitCheck,
    TradingLimitContext,
    TradingLimits,
    TradingLimitViolation,
)


class TradingLimitPolicy:
    def __init__(self, limits: TradingLimits) -> None:
        #: Public and read-only by convention (frozen `TradingLimits`
        #: itself) — a formatter (`trade-once`'s worked display) needs the
        #: configured thresholds alongside `TradingLimitContext`'s raw
        #: numbers, and re-deriving them elsewhere would risk drifting
        #: from what this policy actually checked against.
        self.limits = limits

    def evaluate(self, context: TradingLimitContext) -> tuple[TradingLimitCheck, ...]:
        """@brief Every limit, in a fixed order, always all four — even
        once one has failed. A caller wanting "why is this blocked" wants
        the first failure (`first_violation`); a caller building a
        preview display (`trade-once`'s own worked example shows all four
        with individual ✔ marks) wants the whole set.

        `EPIC-028I` — a protective order or a close passes all four: it is
        reduce-only on Futures (`ExecuteOrderCommand` refuses one that is
        not), so it can open no position, add no notional and is not a new
        trade to pace (`OrderPurpose`).

        `EPIC-029` ADR D6 — a tagged order is judged by its owner's budget
        instead (`_budget_checks`), and that branch runs **before** the
        `only_reduces` return, whatever the purpose: Spot has no reduce-only,
        so a Spot SELL marked CLOSE must still pass the inventory check.
        """
        if context.client_order_tag is not None:
            return self._budget_checks(context)
        if context.purpose.only_reduces:
            return tuple(
                TradingLimitCheck(violation, passed=True) for violation in SIGNAL_LIMITS
            )
        return (
            TradingLimitCheck(
                TradingLimitViolation.MAX_ORDERS_PER_SESSION,
                # BVA: exactly at the cap still passes (it is the Nth
                # order, not the (N+1)th) — `>=` is what stops the
                # *next* one, not this one.
                passed=context.orders_sent_this_session
                < self.limits.max_orders_per_session,
            ),
            TradingLimitCheck(
                TradingLimitViolation.MAX_NOTIONAL_PER_ORDER,
                # BVA: exactly at the cap passes (`≤`, matching this
                # epic's own worked display "notional 128.20 ≤ 500 ✔").
                passed=context.order_notional <= self.limits.max_notional_per_order,
            ),
            TradingLimitCheck(
                TradingLimitViolation.MAX_POSITIONS_PER_SYMBOL,
                passed=context.open_position_count_for_symbol
                < self.limits.max_positions_per_symbol,
            ),
            TradingLimitCheck(
                TradingLimitViolation.MIN_ORDER_INTERVAL,
                # No prior order on this symbol this session -> nothing to
                # be too close to; always passes ("n/a ✔" in the worked
                # example). BVA: exactly `min_order_interval` since the
                # last order passes (`>=`), one tick under it fails.
                passed=(
                    context.time_since_last_order_for_symbol is None
                    or context.time_since_last_order_for_symbol
                    >= self.limits.min_order_interval
                ),
            ),
        )

    def _budget_checks(
        self, context: TradingLimitContext
    ) -> tuple[TradingLimitCheck, ...]:
        """@brief The per-order notional cap (ADR D21), then the five budget
        checks, in a fixed order; or the cap and `OWNER_BUDGET_MISSING` when
        no budget is registered for the tag."""
        notional = TradingLimitCheck(
            TradingLimitViolation.MAX_NOTIONAL_PER_ORDER,
            passed=context.order_notional <= self.limits.max_notional_per_order,
        )
        facts = context.owner_budget
        if facts is None:
            return (
                notional,
                TradingLimitCheck(TradingLimitViolation.OWNER_BUDGET_MISSING, False),
            )
        return (notional, *_owner_budget_checks(facts, context.order_notional))

    def first_violation(
        self, context: TradingLimitContext
    ) -> TradingLimitViolation | None:
        for check in self.evaluate(context):
            if not check.passed:
                return check.violation
        return None


def _owner_budget_checks(
    facts: OwnerBudgetFacts, order_notional: Decimal
) -> tuple[TradingLimitCheck, ...]:
    """@brief ADR D6's five checks. Each counts the order being sent, so a
    figure exactly at its ceiling passes and the next order is refused."""
    budget = facts.budget
    buying = facts.order_side is OrderSide.BUY
    exposure = facts.open_buy_quote + facts.inventory.cost + order_notional
    committed_sell = facts.open_sell_quantity + facts.order_quantity
    return (
        TradingLimitCheck(
            TradingLimitViolation.OWNER_BUDGET_OPEN_ORDERS,
            passed=facts.open_order_count + 1 <= budget.max_open_orders,
        ),
        TradingLimitCheck(
            TradingLimitViolation.OWNER_BUDGET_EXPOSURE,
            passed=not buying or exposure <= budget.max_exposure_quote,
        ),
        TradingLimitCheck(
            TradingLimitViolation.OWNER_BUDGET_SELL_EXCEEDS_INVENTORY,
            passed=buying or committed_sell <= facts.inventory.quantity,
        ),
        TradingLimitCheck(
            TradingLimitViolation.OWNER_BUDGET_SPACING,
            passed=facts.time_since_last_order is None
            or facts.time_since_last_order >= budget.min_order_spacing,
        ),
        TradingLimitCheck(
            TradingLimitViolation.OWNER_BUDGET_RATE,
            passed=facts.orders_in_window + 1 <= budget.max_orders_per_window,
        ),
    )
