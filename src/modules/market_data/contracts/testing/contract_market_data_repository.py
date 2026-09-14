"""The contract suite for `IMarketDataRepository` (HLD §10.3).

Both implementations run it: `FakeMarketDataRepository` in unit,
`SQLAlchemyMarketDataRepository` over a temp directory in integration. A
subclass supplies the `impl` fixture and inherits every assertion.

**Where these guarantees came from.** Not invented — lifted from the 21
integration tests the real repository already had, which were the only written
record of its behaviour. The split was by audience, per HLD §10.3 rule 2:

| Stayed with the real implementation | Promoted here |
| :--- | :--- |
| bulk-insert chunking, shard files on disk, "a read creates no shard", SQLAlchemy's bounded streaming | everything a consumer can observe through the port |

So four tests stayed behind as SQLite concerns, and what is here is what a
backtest handler actually depends on.

**Three semantics worth reading before implementing this port**, because each
is easy to get subtly wrong and each is pinned below:

1. `get_klines()` bounds are **inclusive both ends** — `start_time == end_time`
   returns that one candle.
2. `get_range_coverage()` is the one **half-open** reader, `[start, end)`: the
   candle opening exactly at `end_time` belongs to the next range.
3. `gaps` counts **discontinuities, not missing candles**. A five-minute hole in
   one-minute data is `gaps == 1` with `DataGap.missing_candles == 4`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    DatabaseStatusSnapshot,
    IMarketDataRepository,
)

_MINUTE = TimeFrame.ONE_MINUTE
_T0 = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)


def candle(
    symbol: str = "BTCUSDT",
    minutes: int = 0,
    *,
    interval: TimeFrame = _MINUTE,
    close_price: float = 105.0,
    closed: bool = True,
) -> MarketData:
    """One candle at `_T0 + minutes`, with a `close_time` one cadence later.

    Exported because a consumer writing its own test against the fake needs the
    same shape, and because every assertion below reads better as
    `candle(minutes=3)` than as thirteen keyword arguments. `closed=False`
    leaves `close_time` in the far future, which is how `unclosed_candles` is
    exercised.
    """
    open_time = _T0 + timedelta(minutes=minutes)
    cadence = timedelta(seconds=interval.to_seconds())
    return MarketData(
        symbol=symbol,
        interval=interval.value,
        open_time=open_time,
        open_price=100.0,
        high_price=110.0,
        low_price=90.0,
        close_price=close_price,
        volume=1000.0,
        close_time=open_time + (cadence if closed else timedelta(days=365)),
        quote_asset_volume=105000.0,
        number_of_trades=50,
        taker_buy_base_asset_volume=500.0,
        taker_buy_quote_asset_volume=52500.0,
    )


def at(minutes: int) -> datetime:
    """`_T0 + minutes` — the open time `candle(minutes=...)` carries."""
    return _T0 + timedelta(minutes=minutes)


class MarketDataRepositoryContract:
    """Inherit this and provide `impl`. Every test must pass for both."""

    @pytest.fixture
    def impl(self) -> IMarketDataRepository:
        raise NotImplementedError(
            "a MarketDataRepositoryContract subclass must provide an `impl` "
            "fixture returning the IMarketDataRepository under test"
        )

    # -- writing and reading back --------------------------------------------

    def test_saved_candles_come_back_in_open_time_order(
        self, impl: IMarketDataRepository
    ) -> None:
        """Order is part of the contract: every consumer treats the result as a
        series, and one that arrived shuffled would compute nonsense
        indicators without erroring."""
        impl.save_klines([candle(minutes=2), candle(minutes=0), candle(minutes=1)])

        rows = impl.get_klines("BTCUSDT", _MINUTE)

        assert [row.open_time for row in rows] == [at(0), at(1), at(2)]

    def test_saving_the_same_open_time_again_replaces_it(
        self, impl: IMarketDataRepository
    ) -> None:
        """Upsert on `(symbol, interval, open_time)`, not append. A sync that
        re-fetches an overlapping window relies on it; without it the same
        candle would accumulate and every count would drift."""
        impl.save_klines([candle(minutes=0, close_price=105.0)])

        impl.save_klines([candle(minutes=0, close_price=200.0)])

        rows = impl.get_klines("BTCUSDT", _MINUTE)
        assert len(rows) == 1
        assert rows[0].close_price == 200.0

    def test_reading_a_symbol_that_was_never_written_is_empty_not_an_error(
        self, impl: IMarketDataRepository
    ) -> None:
        assert impl.get_klines("NOSUCHCOIN", _MINUTE) == []
        assert impl.get_latest_kline_time("NOSUCHCOIN", _MINUTE) is None
        assert impl.count_klines("NOSUCHCOIN", _MINUTE) == 0
        assert impl.has_any_klines("NOSUCHCOIN") is False

    def test_symbols_do_not_see_each_others_candles(
        self, impl: IMarketDataRepository
    ) -> None:
        impl.save_klines([candle("BTCUSDT", 0), candle("ETHUSDT", 0)])

        assert len(impl.get_klines("BTCUSDT", _MINUTE)) == 1
        assert len(impl.get_klines("ETHUSDT", _MINUTE)) == 1

    def test_intervals_do_not_see_each_others_candles(
        self, impl: IMarketDataRepository
    ) -> None:
        """The same symbol at two timeframes is two series. Mixing them would
        make every cadence and gap calculation wrong."""
        impl.save_klines(
            [candle(minutes=0), candle(minutes=0, interval=TimeFrame.FIVE_MINUTES)]
        )

        assert len(impl.get_klines("BTCUSDT", _MINUTE)) == 1
        assert len(impl.get_klines("BTCUSDT", TimeFrame.FIVE_MINUTES)) == 1

    # -- filtering -----------------------------------------------------------

    def test_the_time_range_is_inclusive_at_both_ends(
        self, impl: IMarketDataRepository
    ) -> None:
        """`start_time == end_time` selects exactly that candle. The one reader
        that is *not* inclusive is `get_range_coverage()`, below."""
        impl.save_klines([candle(minutes=m) for m in (0, 1, 2)])

        assert [
            row.open_time
            for row in impl.get_klines(
                "BTCUSDT", _MINUTE, start_time=at(1), end_time=at(1)
            )
        ] == [at(1)]
        assert [
            row.open_time
            for row in impl.get_klines("BTCUSDT", _MINUTE, start_time=at(1))
        ] == [at(1), at(2)]

    def test_a_limit_takes_from_the_ordered_start(
        self, impl: IMarketDataRepository
    ) -> None:
        impl.save_klines([candle(minutes=m) for m in (0, 1, 2)])

        assert [
            row.open_time for row in impl.get_klines("BTCUSDT", _MINUTE, limit=2)
        ] == [at(0), at(1)]

    def test_descending_order_reverses_the_series(
        self, impl: IMarketDataRepository
    ) -> None:
        """Together with `limit`, this is how a caller asks for "the newest N"
        — so the limit must apply *after* the ordering, not before."""
        impl.save_klines([candle(minutes=m) for m in (0, 1, 2)])

        rows = impl.get_klines("BTCUSDT", _MINUTE, order_by_desc=True, limit=2)

        assert [row.open_time for row in rows] == [at(2), at(1)]

    def test_the_latest_kline_time_is_the_newest_open_time(
        self, impl: IMarketDataRepository
    ) -> None:
        impl.save_klines([candle(minutes=m) for m in (0, 2, 1)])

        assert impl.get_latest_kline_time("BTCUSDT", _MINUTE) == at(2)

    # -- counting and streaming agree with reading ---------------------------

    def test_counting_agrees_with_reading(self, impl: IMarketDataRepository) -> None:
        """`count_klines()` exists so a caller can size a range without loading
        it (`BUG-025`). If it ever disagreed with `get_klines()`, an
        in-sample/out-of-sample split would be computed against one number and
        executed against another."""
        impl.save_klines([candle(minutes=m) for m in range(5)])

        for kwargs in (
            {},
            {"start_time": at(1)},
            {"end_time": at(3)},
            {"start_time": at(1), "end_time": at(3)},
            {"limit": 2},
        ):
            assert impl.count_klines("BTCUSDT", _MINUTE, **kwargs) == len(
                impl.get_klines("BTCUSDT", _MINUTE, **kwargs)
            ), f"count and get disagree for {kwargs}"

    def test_streaming_yields_what_reading_returns(
        self, impl: IMarketDataRepository
    ) -> None:
        impl.save_klines([candle(minutes=m) for m in range(5)])

        streamed = list(impl.stream_klines("BTCUSDT", _MINUTE))

        assert [row.open_time for row in streamed] == [
            row.open_time for row in impl.get_klines("BTCUSDT", _MINUTE)
        ]

    def test_an_offset_skips_from_the_ordered_start(
        self, impl: IMarketDataRepository
    ) -> None:
        """`offset` + `limit` is how the backtest path fetches an
        out-of-sample tail it has not already streamed (`BUG-025`)."""
        impl.save_klines([candle(minutes=m) for m in range(5)])

        rows = list(impl.stream_klines("BTCUSDT", _MINUTE, offset=3, limit=2))

        assert [row.open_time for row in rows] == [at(3), at(4)]

    # -- reporting -----------------------------------------------------------

    def test_status_of_an_empty_series_is_zeroed_not_absent(
        self, impl: IMarketDataRepository
    ) -> None:
        status = impl.get_database_status("NOSUCHCOIN", _MINUTE)

        assert isinstance(status, DatabaseStatusSnapshot)
        assert status.first_record is None
        assert status.last_record is None
        assert status.total_candles == 0
        assert status.gaps == 0

    def test_status_reports_the_span_and_the_count(
        self, impl: IMarketDataRepository
    ) -> None:
        impl.save_klines([candle(minutes=m) for m in (0, 1, 2)])

        status = impl.get_database_status("BTCUSDT", _MINUTE)

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

        assert impl.get_database_status("BTCUSDT", _MINUTE).gaps == 1

    def test_a_contiguous_series_has_no_gaps(self, impl: IMarketDataRepository) -> None:
        impl.save_klines([candle(minutes=m) for m in range(10)])

        assert impl.get_gaps("BTCUSDT", _MINUTE) == []

    def test_a_gap_names_its_boundaries_and_how_many_are_missing(
        self, impl: IMarketDataRepository
    ) -> None:
        """`start_time` and `end_time` are the candles *around* the hole, not
        the hole itself — `DataGap.fetch_start_time` steps inward from them to
        build the exchange request that repairs it."""
        impl.save_klines([candle(minutes=0), candle(minutes=6)])

        gaps = impl.get_gaps("BTCUSDT", _MINUTE)

        assert len(gaps) == 1
        assert gaps[0].symbol == "BTCUSDT"
        assert gaps[0].interval == _MINUTE
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
            "BTCUSDT", [_MINUTE, TimeFrame.FIVE_MINUTES]
        )

        assert set(statuses) == {_MINUTE.value, TimeFrame.FIVE_MINUTES.value}
        assert statuses[_MINUTE.value].total_candles == 1
        assert statuses[TimeFrame.FIVE_MINUTES.value].total_candles == 0

    def test_status_for_intervals_agrees_with_asking_one_at_a_time(
        self, impl: IMarketDataRepository
    ) -> None:
        """It exists only to save connections, so it must answer identically."""
        impl.save_klines([candle(minutes=m) for m in (0, 1, 5)])

        batch = impl.get_database_status_for_intervals("BTCUSDT", [_MINUTE])

        assert batch[_MINUTE.value] == impl.get_database_status("BTCUSDT", _MINUTE)

    # -- range coverage: the half-open reader --------------------------------

    def test_range_coverage_excludes_the_candle_at_end_time(
        self, impl: IMarketDataRepository
    ) -> None:
        """`[start, end)`. Minutes 0, 1, 3, 4 are stored and `end_time` is
        minute 4, so minute 4 is *not* counted and the last one in range is
        minute 3."""
        impl.save_klines([candle(minutes=m) for m in (0, 1, 3, 4)])

        snapshot = impl.get_range_coverage("BTCUSDT", _MINUTE, at(0), at(4), at(10))

        assert snapshot.first_record == at(0)
        assert snapshot.last_record == at(3)
        assert snapshot.total_candles == 3
        assert snapshot.first_gap_after == at(1)

    def test_range_coverage_of_an_empty_range_is_zeroed(
        self, impl: IMarketDataRepository
    ) -> None:
        snapshot = impl.get_range_coverage("NOSUCHCOIN", _MINUTE, at(0), at(10), at(20))

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

        snapshot = impl.get_range_coverage("BTCUSDT", _MINUTE, at(0), at(5), at(10))

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

        snapshot = impl.get_range_coverage("BTCUSDT", _MINUTE, at(0), at(5), at(2))

        assert snapshot.unclosed_candles == 1

    def test_range_coverage_with_no_start_time_begins_at_the_oldest_candle(
        self, impl: IMarketDataRepository
    ) -> None:
        """`start_time=None` means "all history up to `end_time`" — an
        unbounded request cannot claim a start the caller never gave."""
        impl.save_klines([candle(minutes=m) for m in (2, 3, 4)])

        snapshot = impl.get_range_coverage("BTCUSDT", _MINUTE, None, at(5), at(10))

        assert snapshot.first_record == at(2)
        assert snapshot.total_candles == 3

    # -- deleting ------------------------------------------------------------

    def test_clearing_one_interval_leaves_the_others(
        self, impl: IMarketDataRepository
    ) -> None:
        impl.save_klines(
            [candle(minutes=0), candle(minutes=0, interval=TimeFrame.FIVE_MINUTES)]
        )

        removed = impl.clear_klines("BTCUSDT", _MINUTE)

        assert removed == 1
        assert impl.get_klines("BTCUSDT", _MINUTE) == []
        assert len(impl.get_klines("BTCUSDT", TimeFrame.FIVE_MINUTES)) == 1

    def test_clearing_a_symbol_removes_every_interval(
        self, impl: IMarketDataRepository
    ) -> None:
        impl.save_klines(
            [candle(minutes=0), candle(minutes=0, interval=TimeFrame.FIVE_MINUTES)]
        )

        removed = impl.clear_klines("BTCUSDT")

        assert removed == 2
        assert impl.has_any_klines("BTCUSDT") is False

    def test_clearing_leaves_other_symbols_alone(
        self, impl: IMarketDataRepository
    ) -> None:
        impl.save_klines([candle("BTCUSDT", 0), candle("ETHUSDT", 0)])

        impl.clear_klines("BTCUSDT")

        assert impl.has_any_klines("ETHUSDT") is True

    def test_has_any_klines_is_true_for_data_in_any_interval(
        self, impl: IMarketDataRepository
    ) -> None:
        """Interval-agnostic on purpose (`BUG-078`): a caller deciding whether
        a symbol's storage is safe to delete must not read "empty" from the
        subset of intervals the UI happens to show."""
        impl.save_klines([candle(minutes=0, interval=TimeFrame.FOUR_HOURS)])

        assert impl.has_any_klines("BTCUSDT") is True
        assert impl.get_klines("BTCUSDT", _MINUTE) == []

    def test_available_symbols_are_the_ones_holding_data(
        self, impl: IMarketDataRepository
    ) -> None:
        impl.save_klines([candle("ETHUSDT", 0), candle("BTCUSDT", 0)])

        assert impl.list_available_shards() == ["BTCUSDT", "ETHUSDT"]
