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

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
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
        """
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

    def first_violation(
        self, context: TradingLimitContext
    ) -> TradingLimitViolation | None:
        for check in self.evaluate(context):
            if not check.passed:
                return check.violation
        return None
