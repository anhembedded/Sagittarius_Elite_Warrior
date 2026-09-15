"""`IRangeCoverage`'s contract, against both implementations (HLD §10.3).

The real half is `RangeCoverageService` over `FakeMarketDataRepository` — a
verified fake with its own suite (PR 0.4a-3) — so the real repository read,
the real builder and the real value object all run with nothing to integrate
(`ci-rule.md` §6). SQLite's own aggregate behaviour is
`IMarketDataRepository`'s suite, which runs against the real engine in
`tests/integration/`.

Beyond the shared contract, this file carries the two things only one side
can answer: what the real service computes from stored candles, and what the
fake's scripting helpers do.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.get_backtest_range_coverage import (
    RangeCoverageService,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.backtest_range_coverage import (
    BacktestRangeCoverage,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_range_coverage import (
    IRangeCoverage,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    MINUTE,
    at,
    candle,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.contract_range_coverage import (
    RangeCoverageContract,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_repository import (
    FakeMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_range_coverage import (
    NOTHING_STORED,
    FakeRangeCoverage,
    fully_covered,
)

_NOW = at(10)


class TestFakeRangeCoverage(RangeCoverageContract):
    """The fake's half — what every consumer's test will be driving."""

    @pytest.fixture
    def impl(self) -> IRangeCoverage:
        return FakeRangeCoverage()


class TestTheRealService(RangeCoverageContract):
    """The real one's half — this is what makes the fake *verified*."""

    @pytest.fixture
    def store(self) -> FakeMarketDataRepository:
        return FakeMarketDataRepository()

    @pytest.fixture
    def impl(self, store: FakeMarketDataRepository) -> IRangeCoverage:
        return RangeCoverageService(store)


class TestWhatOnlyTheRealServiceCanAnswer:
    """The arithmetic's own suite is `test_coverage_builders.py`; these two
    prove this service reaches it with the range the caller gave, which no
    test of the builder in isolation can show."""

    def test_a_complete_range_reads_as_fully_covered(self) -> None:
        store = FakeMarketDataRepository()
        store.save_klines([candle("BTCUSDT", minute) for minute in range(5)])

        answer = RangeCoverageService(store).coverage(
            "BTCUSDT", MINUTE, start_time=at(0), end_time=at(5), now=_NOW
        )

        assert answer.is_fully_covered is True
        assert answer.first_open_time == at(0)
        assert answer.last_open_time == at(4)
        assert answer.actual_candles == 5

    def test_a_hole_in_the_middle_is_reported(self) -> None:
        """The whole reason this answer is a value object and not a boolean:
        the screen tells the user *where* history breaks."""
        store = FakeMarketDataRepository()
        store.save_klines(
            [candle("BTCUSDT", minute) for minute in (0, 1, 3, 4)]  # 2 is missing
        )

        answer = RangeCoverageService(store).coverage(
            "BTCUSDT", MINUTE, start_time=at(0), end_time=at(5), now=_NOW
        )

        assert answer.is_fully_covered is False
        assert at(2) in answer.missing_open_times


class TestTheFakesOwnHelpers:
    """`answer_with()`, `was_asked_about()`, `requests` and the two published
    answer builders — not on the port, so the contract suite cannot cover
    them (`BUG-120`'s guard), and the "no" cases are the ones that matter."""

    def test_an_unscripted_symbol_answers_nothing_stored(self) -> None:
        fake = FakeRangeCoverage()

        answer = fake.coverage(
            "BTCUSDT", MINUTE, start_time=at(0), end_time=at(5), now=_NOW
        )

        assert answer == NOTHING_STORED

    def test_a_scripted_answer_comes_back_for_that_symbol(self) -> None:
        fake = FakeRangeCoverage()
        scripted = fully_covered(at(0), at(4), candles=5)
        fake.answer_with(scripted, symbol="BTCUSDT", interval=MINUTE)

        answer = fake.coverage(
            "BTCUSDT", MINUTE, start_time=at(0), end_time=at(5), now=_NOW
        )

        assert answer is scripted

    def test_a_scripted_answer_does_not_leak_to_another_symbol(self) -> None:
        fake = FakeRangeCoverage()
        fake.answer_with(fully_covered(at(0), at(4), candles=5), symbol="BTCUSDT")

        answer = fake.coverage(
            "ETHUSDT", MINUTE, start_time=at(0), end_time=at(5), now=_NOW
        )

        assert answer == NOTHING_STORED

    def test_a_scripted_answer_does_not_leak_to_another_timeframe(self) -> None:
        """A screen asking about the daily candles of a symbol whose minute
        range is complete must not be told it is complete."""
        fake = FakeRangeCoverage()
        fake.answer_with(
            fully_covered(at(0), at(4), candles=5), symbol="BTCUSDT", interval=MINUTE
        )

        answer = fake.coverage(
            "BTCUSDT",
            TimeFrame.ONE_DAY,
            start_time=at(0),
            end_time=at(5),
            now=_NOW,
        )

        assert answer == NOTHING_STORED

    def test_a_sample_longer_than_the_cap_is_refused(self) -> None:
        """The fake refuses to answer what production cannot: the real path
        truncates the sample, so a test scripting five missing opens would be
        asserting against an impossible answer."""
        fake = FakeRangeCoverage()
        too_many = BacktestRangeCoverage(
            is_fully_covered=False,
            first_open_time=at(0),
            last_open_time=at(9),
            expected_candles=10,
            actual_candles=5,
            duplicate_candles=0,
            missing_open_times=tuple(at(minute) for minute in range(5)),
            has_unclosed_candle=False,
        )

        with pytest.raises(ValueError, match="sample truncated"):
            fake.answer_with(too_many)

    def test_was_asked_about_says_no_before_anything_was_asked(self) -> None:
        assert FakeRangeCoverage().was_asked_about("BTCUSDT") is False

    def test_was_asked_about_says_no_for_a_symbol_nobody_asked_about(self) -> None:
        fake = FakeRangeCoverage()

        fake.coverage("BTCUSDT", MINUTE, start_time=None, end_time=at(5), now=_NOW)

        assert fake.was_asked_about("ETHUSDT") is False

    def test_the_timeframe_narrows_was_asked_about(self) -> None:
        fake = FakeRangeCoverage()

        fake.coverage("BTCUSDT", MINUTE, start_time=None, end_time=at(5), now=_NOW)

        assert fake.was_asked_about("BTCUSDT", MINUTE) is True
        assert fake.was_asked_about("BTCUSDT", TimeFrame.ONE_DAY) is False

    def test_requests_record_the_range_the_caller_asked_for(self) -> None:
        """What the Backtest screen's tests assert: the date range the user
        picked reached the module, not a default."""
        fake = FakeRangeCoverage()

        fake.coverage("BTCUSDT", MINUTE, start_time=at(1), end_time=at(9), now=_NOW)

        request = fake.requests[0]
        assert (request.start_time, request.end_time, request.now) == (
            at(1),
            at(9),
            _NOW,
        )

    def test_nothing_stored_is_the_shape_a_screen_can_tell_apart(self) -> None:
        """Guards the published constant itself: a screen branches on these
        exact fields to choose "sync this" over "part of this is missing"."""
        assert NOTHING_STORED.is_fully_covered is False
        assert NOTHING_STORED.first_open_time is None
        assert NOTHING_STORED.last_open_time is None
        assert NOTHING_STORED.actual_candles == 0

    def test_fully_covered_builds_the_complete_shape(self) -> None:
        answer = fully_covered(at(0), at(4), candles=5)

        assert answer.is_fully_covered is True
        assert answer.missing_open_times == ()
        assert answer.expected_candles == answer.actual_candles == 5
        assert answer.has_unclosed_candle is False
