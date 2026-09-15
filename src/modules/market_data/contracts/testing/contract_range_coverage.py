"""The contract suite for `IRangeCoverage` (HLD §10.3).

Both implementations run it: `FakeRangeCoverage`, and the real
`RangeCoverageService` over `FakeMarketDataRepository`.

**It is deliberately short, and the reason is where the truth lives.** The
coverage *arithmetic* — expected candle counts, which holes are reported,
what "fully covered" means at a range's edges — belongs to
`coverage_builders.py` and has its own thorough suite
(`test_coverage_builders.py`). Restating any of it here would give the app two
answers to one question, and the fake would have to re-derive it from candles
to pass, which is exactly the second implementation of the arithmetic HLD §3.4
keeps inside the module.

What every implementation must promise, and what this pins, is the shape a
screen renders: an untouched range still answers, with a real
`BacktestRangeCoverage` that says nothing is stored. `BUG-072` is why that is
a contract and not an assumption — a loose test double answered with a
response envelope, and it reached a Qt signal typed `object` and crashed the
interpreter.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.backtest_range_coverage import (
    MAX_REPORTED_MISSING_OPENS,
    BacktestRangeCoverage,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_range_coverage import (
    IRangeCoverage,
)

_MINUTE = TimeFrame.ONE_MINUTE
_FROM = datetime(2024, 1, 1, tzinfo=UTC)
_TO = datetime(2024, 1, 2, tzinfo=UTC)
_NOW = datetime(2024, 1, 3, tzinfo=UTC)


class RangeCoverageContract:
    """Inherit this and provide `impl`. Both implementations must pass it."""

    @pytest.fixture
    def impl(self) -> IRangeCoverage:
        raise NotImplementedError(
            "a RangeCoverageContract subclass must provide an `impl` fixture "
            "returning the IRangeCoverage under test"
        )

    def test_a_range_with_nothing_stored_still_answers(
        self, impl: IRangeCoverage
    ) -> None:
        """The ordinary state of a symbol the user has not synced. Raising
        would make the normal case exceptional, and returning `None` would
        reach a Qt signal typed `object` (`BUG-072`)."""
        answer = impl.coverage(
            "NOSUCHPAIR", _MINUTE, start_time=_FROM, end_time=_TO, now=_NOW
        )

        assert isinstance(answer, BacktestRangeCoverage)

    def test_nothing_stored_reads_as_nothing_stored_not_as_a_gap(
        self, impl: IRangeCoverage
    ) -> None:
        """A screen renders these two differently: "you have none of this" is
        a sync suggestion, "you have most of this" is a warning. Both bounds
        `None` is what distinguishes them."""
        answer = impl.coverage(
            "NOSUCHPAIR", _MINUTE, start_time=_FROM, end_time=_TO, now=_NOW
        )

        assert answer.is_fully_covered is False
        assert answer.first_open_time is None
        assert answer.last_open_time is None
        assert answer.actual_candles == 0

    def test_an_unbounded_start_is_accepted(self, impl: IRangeCoverage) -> None:
        """`start_time=None` means "from the first candle stored", which is
        what a user who left the range open asks for — an implementation that
        required a start would break the screen's default state."""
        answer = impl.coverage(
            "NOSUCHPAIR", _MINUTE, start_time=None, end_time=_TO, now=_NOW
        )

        assert isinstance(answer, BacktestRangeCoverage)

    def test_the_missing_sample_is_never_longer_than_the_cap(
        self, impl: IRangeCoverage
    ) -> None:
        """`missing_open_times` is a sample, never a list: a year of
        1-minute candles with one wide hole has hundreds of thousands of
        missing opens, and a caller that treated its length as the count
        would be reporting a number it never had."""
        answer = impl.coverage(
            "NOSUCHPAIR", _MINUTE, start_time=_FROM, end_time=_TO, now=_NOW
        )

        assert len(answer.missing_open_times) <= MAX_REPORTED_MISSING_OPENS
