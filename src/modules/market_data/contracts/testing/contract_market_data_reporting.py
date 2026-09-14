"""What the store says *about* itself: status, gaps, and range coverage.

One of the three parts of `IMarketDataRepository`'s contract suite — see
`contract_market_data_repository.py`. These are the guarantees a consumer
reads when it is deciding whether the data is usable, rather than reading the
data itself, and two of them are the ones most easily got wrong: `gaps` counts
discontinuities, not missing candles, and `get_range_coverage()` is half-open
where every other reader is inclusive.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    DatabaseStatusSnapshot,
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    MINUTE,
    at,
    candle,
)


class MarketDataReportingContract:
    """Part of `MarketDataRepositoryContract`; see that class. A subclass
    supplies the `impl` fixture."""

    # -- reporting -----------------------------------------------------------

    def test_status_of_an_empty_series_is_zeroed_not_absent(
        self, impl: IMarketDataRepository
    ) -> None:
        status = impl.get_database_status("NOSUCHCOIN", MINUTE)

        assert isinstance(status, DatabaseStatusSnapshot)
        assert status.first_record is None
        assert status.last_record is None
        assert status.total_candles == 0
        assert status.gaps == 0

    def test_status_reports_the_span_and_the_count(
        self, impl: IMarketDataRepository
    ) -> None:
        impl.save_klines([candle(minutes=m) for m in (0, 1, 2)])

        status = impl.get_database_status("BTCUSDT", MINUTE)

        assert status.first_record == at(0)
        assert status.last_record == at(2)
        assert status.total_candles == 3
        assert status.gaps == 0

    def test_gaps_counts_discontinuities_not_missing_candles(
        self, impl: IMarketDataRepository
    ) -> None:
        """The distinction that bites: minutes 2, 3 and 4 are all missing, and
        that is **one** gap. A reader treating `gaps` as a candle count would
        report a five-minute outage as five separate problems."""
        impl.save_klines([candle(minutes=m) for m in (0, 1, 5)])

        assert impl.get_database_status("BTCUSDT", MINUTE).gaps == 1

    def test_a_contiguous_series_has_no_gaps(self, impl: IMarketDataRepository) -> None:
        impl.save_klines([candle(minutes=m) for m in range(10)])

        assert impl.get_gaps("BTCUSDT", MINUTE) == []

    def test_a_gap_names_its_boundaries_and_how_many_are_missing(
        self, impl: IMarketDataRepository
    ) -> None:
        """`start_time` and `end_time` are the candles *around* the hole, not
        the hole itself — `DataGap.fetch_start_time` steps inward from them to
        build the exchange request that repairs it."""
        impl.save_klines([candle(minutes=0), candle(minutes=6)])

        gaps = impl.get_gaps("BTCUSDT", MINUTE)

        assert len(gaps) == 1
        assert gaps[0].symbol == "BTCUSDT"
        assert gaps[0].interval == MINUTE
        assert gaps[0].start_time == at(0)
        assert gaps[0].end_time == at(6)
        assert gaps[0].missing_candles == 5

    def test_status_for_intervals_answers_every_interval_asked_for(
        self, impl: IMarketDataRepository
    ) -> None:
        """Keyed by `TimeFrame.value`, and an interval holding nothing still
        gets an entry — a caller rendering a grid must not have to guess at a
        missing key (`BUG-078`)."""
        impl.save_klines([candle(minutes=0)])

        statuses = impl.get_database_status_for_intervals(
            "BTCUSDT", [MINUTE, TimeFrame.FIVE_MINUTES]
        )

        assert set(statuses) == {MINUTE.value, TimeFrame.FIVE_MINUTES.value}
        assert statuses[MINUTE.value].total_candles == 1
        assert statuses[TimeFrame.FIVE_MINUTES.value].total_candles == 0

    def test_status_for_intervals_agrees_with_asking_one_at_a_time(
        self, impl: IMarketDataRepository
    ) -> None:
        """It exists only to save connections, so it must answer identically."""
        impl.save_klines([candle(minutes=m) for m in (0, 1, 5)])

        batch = impl.get_database_status_for_intervals("BTCUSDT", [MINUTE])

        assert batch[MINUTE.value] == impl.get_database_status("BTCUSDT", MINUTE)

    # -- range coverage: the half-open reader --------------------------------

    def test_range_coverage_excludes_the_candle_at_end_time(
        self, impl: IMarketDataRepository
    ) -> None:
        """`[start, end)`. Minutes 0, 1, 3, 4 are stored and `end_time` is
        minute 4, so minute 4 is *not* counted and the last one in range is
        minute 3."""
        impl.save_klines([candle(minutes=m) for m in (0, 1, 3, 4)])

        snapshot = impl.get_range_coverage("BTCUSDT", MINUTE, at(0), at(4), at(10))

        assert snapshot.first_record == at(0)
        assert snapshot.last_record == at(3)
        assert snapshot.total_candles == 3
        assert snapshot.first_gap_after == at(1)

    def test_range_coverage_of_an_empty_range_is_zeroed(
        self, impl: IMarketDataRepository
    ) -> None:
        snapshot = impl.get_range_coverage("NOSUCHCOIN", MINUTE, at(0), at(10), at(20))

        assert snapshot.first_record is None
        assert snapshot.last_record is None
        assert snapshot.total_candles == 0
        assert snapshot.distinct_candles == 0
        assert snapshot.first_gap_after is None
        assert snapshot.unclosed_candles == 0

    def test_range_coverage_reports_no_gap_for_a_contiguous_range(
        self, impl: IMarketDataRepository
    ) -> None:
        impl.save_klines([candle(minutes=m) for m in range(5)])

        snapshot = impl.get_range_coverage("BTCUSDT", MINUTE, at(0), at(5), at(10))

        assert snapshot.total_candles == 5
        assert snapshot.distinct_candles == 5
        assert snapshot.first_gap_after is None

    def test_range_coverage_counts_a_still_forming_candle(
        self, impl: IMarketDataRepository
    ) -> None:
        """A candle whose `close_time` is after `now` has not finished, so a
        backtest including it would score a partial bar as a whole one. The
        coverage report says so rather than silently including it."""
        impl.save_klines([candle(minutes=0), candle(minutes=1, closed=False)])

        snapshot = impl.get_range_coverage("BTCUSDT", MINUTE, at(0), at(5), at(2))

        assert snapshot.unclosed_candles == 1

    def test_range_coverage_with_no_start_time_begins_at_the_oldest_candle(
        self, impl: IMarketDataRepository
    ) -> None:
        """`start_time=None` means "all history up to `end_time`" — an
        unbounded request cannot claim a start the caller never gave."""
        impl.save_klines([candle(minutes=m) for m in (2, 3, 4)])

        snapshot = impl.get_range_coverage("BTCUSDT", MINUTE, None, at(5), at(10))

        assert snapshot.first_record == at(2)
        assert snapshot.total_candles == 3
