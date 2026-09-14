"""What the store keeps and hands back: writing, reading, filtering, counting.

One of the three parts of `IMarketDataRepository`'s contract suite — see
`contract_market_data_repository.py`, which composes them and explains the
three semantics that are easy to get wrong. Split because one class holding
all twenty-nine guarantees was 439 lines and 30 public methods, over both
thresholds `architecture-rule.md` §5 rule 4 calls non-negotiable, tests
included (rule 6).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    MINUTE,
    at,
    candle,
)


class MarketDataStorageContract:
    """Part of `MarketDataRepositoryContract`; see that class. A subclass
    supplies the `impl` fixture."""

    # -- writing and reading back --------------------------------------------

    def test_saved_candles_come_back_in_open_time_order(
        self, impl: IMarketDataRepository
    ) -> None:
        """Order is part of the contract: every consumer treats the result as a
        series, and one that arrived shuffled would compute nonsense
        indicators without erroring."""
        impl.save_klines([candle(minutes=2), candle(minutes=0), candle(minutes=1)])

        rows = impl.get_klines("BTCUSDT", MINUTE)

        assert [row.open_time for row in rows] == [at(0), at(1), at(2)]

    def test_saving_the_same_open_time_again_replaces_it(
        self, impl: IMarketDataRepository
    ) -> None:
        """Upsert on `(symbol, interval, open_time)`, not append. A sync that
        re-fetches an overlapping window relies on it; without it the same
        candle would accumulate and every count would drift."""
        impl.save_klines([candle(minutes=0, close_price=105.0)])

        impl.save_klines([candle(minutes=0, close_price=200.0)])

        rows = impl.get_klines("BTCUSDT", MINUTE)
        assert len(rows) == 1
        assert rows[0].close_price == 200.0

    def test_reading_a_symbol_that_was_never_written_is_empty_not_an_error(
        self, impl: IMarketDataRepository
    ) -> None:
        assert impl.get_klines("NOSUCHCOIN", MINUTE) == []
        assert impl.get_latest_kline_time("NOSUCHCOIN", MINUTE) is None
        assert impl.count_klines("NOSUCHCOIN", MINUTE) == 0
        assert impl.has_any_klines("NOSUCHCOIN") is False

    def test_symbols_do_not_see_each_others_candles(
        self, impl: IMarketDataRepository
    ) -> None:
        impl.save_klines([candle("BTCUSDT", 0), candle("ETHUSDT", 0)])

        assert len(impl.get_klines("BTCUSDT", MINUTE)) == 1
        assert len(impl.get_klines("ETHUSDT", MINUTE)) == 1

    def test_intervals_do_not_see_each_others_candles(
        self, impl: IMarketDataRepository
    ) -> None:
        """The same symbol at two timeframes is two series. Mixing them would
        make every cadence and gap calculation wrong."""
        impl.save_klines(
            [candle(minutes=0), candle(minutes=0, interval=TimeFrame.FIVE_MINUTES)]
        )

        assert len(impl.get_klines("BTCUSDT", MINUTE)) == 1
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
                "BTCUSDT", MINUTE, start_time=at(1), end_time=at(1)
            )
        ] == [at(1)]
        assert [
            row.open_time
            for row in impl.get_klines("BTCUSDT", MINUTE, start_time=at(1))
        ] == [at(1), at(2)]

    def test_a_limit_takes_from_the_ordered_start(
        self, impl: IMarketDataRepository
    ) -> None:
        impl.save_klines([candle(minutes=m) for m in (0, 1, 2)])

        assert [
            row.open_time for row in impl.get_klines("BTCUSDT", MINUTE, limit=2)
        ] == [at(0), at(1)]

    def test_descending_order_reverses_the_series(
        self, impl: IMarketDataRepository
    ) -> None:
        """Together with `limit`, this is how a caller asks for "the newest N"
        — so the limit must apply *after* the ordering, not before."""
        impl.save_klines([candle(minutes=m) for m in (0, 1, 2)])

        rows = impl.get_klines("BTCUSDT", MINUTE, order_by_desc=True, limit=2)

        assert [row.open_time for row in rows] == [at(2), at(1)]

    def test_the_latest_kline_time_is_the_newest_open_time(
        self, impl: IMarketDataRepository
    ) -> None:
        impl.save_klines([candle(minutes=m) for m in (0, 2, 1)])

        assert impl.get_latest_kline_time("BTCUSDT", MINUTE) == at(2)

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
            assert impl.count_klines("BTCUSDT", MINUTE, **kwargs) == len(
                impl.get_klines("BTCUSDT", MINUTE, **kwargs)
            ), f"count and get disagree for {kwargs}"

    def test_streaming_yields_what_reading_returns(
        self, impl: IMarketDataRepository
    ) -> None:
        impl.save_klines([candle(minutes=m) for m in range(5)])

        streamed = list(impl.stream_klines("BTCUSDT", MINUTE))

        assert [row.open_time for row in streamed] == [
            row.open_time for row in impl.get_klines("BTCUSDT", MINUTE)
        ]

    def test_an_offset_skips_from_the_ordered_start(
        self, impl: IMarketDataRepository
    ) -> None:
        """`offset` + `limit` is how the backtest path fetches an
        out-of-sample tail it has not already streamed (`BUG-025`)."""
        impl.save_klines([candle(minutes=m) for m in range(5)])

        rows = list(impl.stream_klines("BTCUSDT", MINUTE, offset=3, limit=2))

        assert [row.open_time for row in rows] == [at(3), at(4)]
