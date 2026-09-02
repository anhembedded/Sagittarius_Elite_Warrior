from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.domain.trading.policies.trading_limit_policy import (
    TradingLimitContext,
    TradingLimitPolicy,
    TradingLimits,
    TradingLimitViolation,
)

_LIMITS = TradingLimits(
    max_orders_per_session=20,
    max_notional_per_order=Decimal(500),
    max_positions_per_symbol=1,
    min_order_interval=timedelta(seconds=60),
)


def _context(**overrides: object) -> TradingLimitContext:
    defaults: dict[str, object] = {
        "orders_sent_this_session": 0,
        "order_notional": Decimal(100),
        "open_position_count_for_symbol": 0,
        "time_since_last_order_for_symbol": None,
    }
    defaults.update(overrides)
    return TradingLimitContext(**defaults)  # type: ignore[arg-type]


def _policy() -> TradingLimitPolicy:
    return TradingLimitPolicy(_LIMITS)


class TestMaxOrdersPerSession:
    def test_below_the_cap_passes(self) -> None:
        assert _policy().first_violation(_context(orders_sent_this_session=18)) is None

    def test_exactly_at_the_cap_passes(self) -> None:
        """BVA: 20 orders already sent this session means this is the 20th
        — still within the 20-order cap."""
        assert _policy().first_violation(_context(orders_sent_this_session=19)) is None

    def test_one_over_the_cap_is_blocked(self) -> None:
        assert (
            _policy().first_violation(_context(orders_sent_this_session=20))
            is TradingLimitViolation.MAX_ORDERS_PER_SESSION
        )

    def test_mutation_verify_ge_not_gt(self) -> None:
        """Guards against `>` being substituted for `<` in the policy's
        own comparison (`testing-rule.md` §2's asked-for mutation check,
        stated as ">= vs >" from the check's blocking side): at
        `orders_sent_this_session == max_orders_per_session`, the next
        order MUST be blocked. A policy using the wrong comparison
        operator would let it through."""
        context = _context(orders_sent_this_session=_LIMITS.max_orders_per_session)
        assert (
            _policy().first_violation(context)
            is TradingLimitViolation.MAX_ORDERS_PER_SESSION
        )


class TestMaxNotionalPerOrder:
    def test_below_the_cap_passes(self) -> None:
        assert _policy().first_violation(_context(order_notional=Decimal(499))) is None

    def test_exactly_at_the_cap_passes(self) -> None:
        assert _policy().first_violation(_context(order_notional=Decimal(500))) is None

    def test_one_over_the_cap_is_blocked(self) -> None:
        assert (
            _policy().first_violation(_context(order_notional=Decimal("500.01")))
            is TradingLimitViolation.MAX_NOTIONAL_PER_ORDER
        )


class TestMaxPositionsPerSymbol:
    def test_flat_passes(self) -> None:
        assert (
            _policy().first_violation(_context(open_position_count_for_symbol=0))
            is None
        )

    def test_one_open_position_is_blocked(self) -> None:
        """This epic's own worked example (`EPIC-021G` §5): an existing
        open position on the symbol blocks a second order outright."""
        assert (
            _policy().first_violation(_context(open_position_count_for_symbol=1))
            is TradingLimitViolation.MAX_POSITIONS_PER_SYMBOL
        )


class TestMinOrderInterval:
    def test_no_prior_order_passes(self) -> None:
        assert (
            _policy().first_violation(_context(time_since_last_order_for_symbol=None))
            is None
        )

    def test_exactly_at_the_interval_passes(self) -> None:
        assert (
            _policy().first_violation(
                _context(time_since_last_order_for_symbol=timedelta(seconds=60))
            )
            is None
        )

    def test_one_second_under_the_interval_is_blocked(self) -> None:
        assert (
            _policy().first_violation(
                _context(time_since_last_order_for_symbol=timedelta(seconds=59))
            )
            is TradingLimitViolation.MIN_ORDER_INTERVAL
        )


class TestEvaluateReturnsAllFour:
    def test_all_four_checks_present_even_when_only_one_fails(self) -> None:
        checks = _policy().evaluate(_context(open_position_count_for_symbol=1))

        assert {check.violation for check in checks} == {
            TradingLimitViolation.MAX_ORDERS_PER_SESSION,
            TradingLimitViolation.MAX_NOTIONAL_PER_ORDER,
            TradingLimitViolation.MAX_POSITIONS_PER_SYMBOL,
            TradingLimitViolation.MIN_ORDER_INTERVAL,
        }
        failed = {check.violation for check in checks if not check.passed}
        assert failed == {TradingLimitViolation.MAX_POSITIONS_PER_SYMBOL}

    def test_first_violation_is_none_when_everything_passes(self) -> None:
        assert _policy().first_violation(_context()) is None
