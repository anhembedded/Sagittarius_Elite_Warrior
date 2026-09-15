"""The contract suite for `IHistoricalKlines` (HLD §10.3).

Both implementations run it: `FakeHistoricalKlines`, and the real
`StoredKlinesReader` over a repository. The subclass supplies
`impl` and a `seed` callable, because the two put rows in by different means —
the fake has its own store, the reader reads `IMarketDataRepository` — and
that asymmetry belongs in the adapter-shaped place rather than in the
contract.

What this pins is the promise a consumer reads the docstring for: an unknown
symbol is empty rather than an error, bounds are inclusive, `limit` caps after
ordering, `newest_first` changes *which* rows survive a limit and not only
their order, and `load_many` answers for every symbol asked about. What it does
not pin is SQLite's own behaviour; `tests/integration/` runs the same suite
against the real repository for that.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    MINUTE,
    at,
    candle,
)

_MINUTE = MINUTE

#: How a subclass puts rows where its implementation will read them.
type SeedKlines = Callable[[Sequence[MarketData]], None]


def _minute_candle(
    symbol: str, minutes: int, *, interval: TimeFrame = MINUTE
) -> MarketData:
    """`candles.candle()` with the close price set to the minute offset.

    The builder is reused rather than reimplemented — it already knows
    `MarketData`'s thirteen fields and the `close_time` cadence. Only the
    close is overridden, so that `close == 4.0` reads as "the candle from
    minute 4" in an ordering assertion without a second lookup
    (`onb` §8 trap 2: assert on content, not on counts).
    """
    return candle(symbol, minutes, interval=interval, close_price=float(minutes))


def _closes(rows: Sequence[MarketData]) -> list[float]:
    return [row.close_price for row in rows]


class HistoricalKlinesContract:
    """Inherit this, provide `impl` and `seed`. Both must pass all of it."""

    @pytest.fixture
    def impl(self) -> IHistoricalKlines:
        raise NotImplementedError(
            "a HistoricalKlinesContract subclass must provide an `impl` fixture "
            "returning the IHistoricalKlines under test"
        )

    @pytest.fixture
    def seed(self) -> SeedKlines:
        raise NotImplementedError(
            "a HistoricalKlinesContract subclass must provide a `seed` fixture "
            "that puts rows where its implementation reads them"
        )

    # -- nothing stored is not a failure -------------------------------------

    def test_an_unknown_symbol_reads_empty(self, impl: IHistoricalKlines) -> None:
        """The ordinary state of a symbol the user has not synced. Every
        caller handles it by drawing an empty chart and saying so; raising
        would make the normal case exceptional."""
        assert impl.load("NOSUCHPAIR", _MINUTE) == ()

    def test_a_symbol_stored_at_another_interval_reads_empty(
        self, impl: IHistoricalKlines, seed: SeedKlines
    ) -> None:
        """One symbol's 1m and 1d rows are different series. Mixing them would
        put day candles on a minute chart, which the screen cannot tell apart
        from real data."""
        seed([_minute_candle("BTCUSDT", 0, interval=TimeFrame.ONE_DAY)])

        assert impl.load("BTCUSDT", _MINUTE) == ()

    # -- order and selection -------------------------------------------------

    def test_rows_come_back_oldest_first_by_default(
        self, impl: IHistoricalKlines, seed: SeedKlines
    ) -> None:
        seed(
            [
                _minute_candle("BTCUSDT", 2),
                _minute_candle("BTCUSDT", 0),
                _minute_candle("BTCUSDT", 1),
            ]
        )

        assert _closes(impl.load("BTCUSDT", _MINUTE)) == [0.0, 1.0, 2.0]

    def test_newest_first_reverses_the_order(
        self, impl: IHistoricalKlines, seed: SeedKlines
    ) -> None:
        seed(
            [
                _minute_candle("BTCUSDT", 0),
                _minute_candle("BTCUSDT", 1),
                _minute_candle("BTCUSDT", 2),
            ]
        )

        rows = impl.load("BTCUSDT", _MINUTE, newest_first=True)

        assert _closes(rows) == [2.0, 1.0, 0.0]

    def test_a_limit_caps_how_many_rows_come_back(
        self, impl: IHistoricalKlines, seed: SeedKlines
    ) -> None:
        seed([_minute_candle("BTCUSDT", minute) for minute in range(5)])

        assert _closes(impl.load("BTCUSDT", _MINUTE, limit=2)) == [0.0, 1.0]

    def test_newest_first_decides_which_rows_a_limit_keeps(
        self, impl: IHistoricalKlines, seed: SeedKlines
    ) -> None:
        """The reason three callers pass it: they want the *most recent* N, not
        the first N. A limit applied before the ordering would hand a live
        chart the oldest candles in the shard and look identical in type."""
        seed([_minute_candle("BTCUSDT", minute) for minute in range(5)])

        rows = impl.load("BTCUSDT", _MINUTE, limit=2, newest_first=True)

        assert _closes(rows) == [4.0, 3.0]

    # -- the range bounds ----------------------------------------------------

    def test_both_range_bounds_are_inclusive(
        self, impl: IHistoricalKlines, seed: SeedKlines
    ) -> None:
        """Inclusive on both ends, which is what the real `get_klines()` does.
        A caller computing a half-open window would silently lose one candle
        per query, and a missing newest candle is exactly what a chart cannot
        show you is missing."""
        seed([_minute_candle("BTCUSDT", minute) for minute in range(5)])

        rows = impl.load(
            "BTCUSDT",
            _MINUTE,
            start_time=at(1),
            end_time=at(3),
        )

        assert _closes(rows) == [1.0, 2.0, 3.0]

    # -- many symbols --------------------------------------------------------

    def test_every_symbol_asked_about_appears_in_the_answer(
        self, impl: IHistoricalKlines, seed: SeedKlines
    ) -> None:
        """Including one with nothing stored, mapped to an empty tuple: a
        caller iterates its own request without checking for the key, and a
        symbol that vanished from the answer can never be read as a symbol
        with no rows."""
        seed([_minute_candle("BTCUSDT", 0)])

        rows = impl.load_many(["BTCUSDT", "ETHUSDT"], _MINUTE)

        assert set(rows) == {"BTCUSDT", "ETHUSDT"}
        assert _closes(rows["BTCUSDT"]) == [0.0]
        assert rows["ETHUSDT"] == ()

    def test_one_symbols_rows_never_appear_under_another(
        self, impl: IHistoricalKlines, seed: SeedKlines
    ) -> None:
        seed([_minute_candle("BTCUSDT", 0), _minute_candle("ETHUSDT", 1)])

        rows = impl.load_many(["BTCUSDT", "ETHUSDT"], _MINUTE)

        assert _closes(rows["BTCUSDT"]) == [0.0]
        assert _closes(rows["ETHUSDT"]) == [1.0]

    def test_asking_about_no_symbols_reads_an_empty_mapping(
        self, impl: IHistoricalKlines
    ) -> None:
        """A screen with an empty symbol list is not an error here — it has
        simply nothing to draw, and the real path must not build a thread pool
        for it either."""
        assert dict(impl.load_many([], _MINUTE)) == {}

    def test_the_range_and_the_limit_apply_per_symbol(
        self, impl: IHistoricalKlines, seed: SeedKlines
    ) -> None:
        """Not to the combined result: two symbols asked for 2 candles each
        must yield 2 each, never 2 in total. A limit applied to the union
        would leave one chart blank at random."""
        seed(
            [_minute_candle("BTCUSDT", minute) for minute in range(4)]
            + [_minute_candle("ETHUSDT", minute) for minute in range(4)]
        )

        rows = impl.load_many(["BTCUSDT", "ETHUSDT"], _MINUTE, limit=2)

        assert _closes(rows["BTCUSDT"]) == [0.0, 1.0]
        assert _closes(rows["ETHUSDT"]) == [0.0, 1.0]

    # -- the snapshot is a snapshot ------------------------------------------

    def test_the_result_is_an_immutable_snapshot(
        self, impl: IHistoricalKlines, seed: SeedKlines
    ) -> None:
        """`domain-truth-rule.md` — a caller that appends to the rows is not
        telling anyone, and the next reader would see a chart's local edit as
        stored data."""
        seed([_minute_candle("BTCUSDT", 0)])

        rows = impl.load("BTCUSDT", _MINUTE)

        assert isinstance(rows, tuple)
        assert isinstance(impl.load_many(["BTCUSDT"], _MINUTE)["BTCUSDT"], tuple)
