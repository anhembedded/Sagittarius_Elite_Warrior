"""`EPIC-021G` — the domain policy that decides whether a live order may be
sent at all, independent of whether the order itself is well-formed.

@details A business decision, not a coordinator's `if`: it must be
testable with zero network (`testing-rule.md` §1), and it is the one
mechanism in this epic that stops a bad signal loop from firing hundreds
of orders (§1's stated real risk). All four limits are on by default —
there is no "disable this one limit" toggle; only their numeric
thresholds are configurable (`ConfigKeys` §`TRADING_MAX_*`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from enum import Enum


class TradingLimitViolation(str, Enum):
    """@brief Which of the four limits blocked an order — named so a
    caller (and a human reading a log line) never has to infer it from a
    bare `False`."""

    MAX_ORDERS_PER_SESSION = "max_orders_per_session"
    MAX_NOTIONAL_PER_ORDER = "max_notional_per_order"
    MAX_POSITIONS_PER_SYMBOL = "max_positions_per_symbol"
    MIN_ORDER_INTERVAL = "min_order_interval"


@dataclass(frozen=True)
class TradingLimits:
    """Configured thresholds — see `ConfigKeys.TRADING_MAX_ORDERS_PER_SESSION`
    et al. for where these come from at runtime."""

    max_orders_per_session: int
    max_notional_per_order: Decimal
    max_positions_per_symbol: int
    min_order_interval: timedelta


@dataclass(frozen=True)
class TradingLimitContext:
    """The live, per-attempt facts `TradingLimitPolicy` checks against
    `TradingLimits`. Sourced from `TradingSessionState`, never from a
    fresh network call per order — reconciliation happens once, at
    `EnableTradingCommand` time (`ADR §4`)."""

    orders_sent_this_session: int
    order_notional: Decimal
    open_position_count_for_symbol: int
    time_since_last_order_for_symbol: timedelta | None


@dataclass(frozen=True)
class TradingLimitCheck:
    violation: TradingLimitViolation
    passed: bool


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
