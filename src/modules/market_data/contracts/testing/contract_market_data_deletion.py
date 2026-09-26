"""What deleting removes, and what it must leave alone.

One of the three parts of `IMarketDataRepository`'s contract suite — see
`contract_market_data_repository.py`. `BUG-078` is the reason
`has_any_klines()` is pinned here: a caller deciding whether a symbol's
storage is safe to delete must not judge "empty" against only the intervals
the UI happens to show.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    MINUTE,
    candle,
)

#: `EPIC-027A` added `market` to every call; Spot is this app's only real,
#: measured market data source today (see `contract_market_data_storage.py`).
SPOT = MarketType.SPOT
FUTURES = MarketType.FUTURES_USD_M


class MarketDataDeletionContract:
    """Part of `MarketDataRepositoryContract`; see that class. A subclass
    supplies the `impl` fixture."""

    # -- deleting ------------------------------------------------------------

    def test_clearing_one_interval_leaves_the_others(
        self, impl: IMarketDataRepository
    ) -> None:
        impl.save_klines(
            SPOT,
            [candle(minutes=0), candle(minutes=0, interval=TimeFrame.FIVE_MINUTES)],
        )

        removed = impl.clear_klines(SPOT, "BTCUSDT", MINUTE)

        assert removed == 1
        assert impl.get_klines(SPOT, "BTCUSDT", MINUTE) == []
        assert len(impl.get_klines(SPOT, "BTCUSDT", TimeFrame.FIVE_MINUTES)) == 1

    def test_clearing_a_symbol_removes_every_interval(
        self, impl: IMarketDataRepository
    ) -> None:
        impl.save_klines(
            SPOT,
            [candle(minutes=0), candle(minutes=0, interval=TimeFrame.FIVE_MINUTES)],
        )

        removed = impl.clear_klines(SPOT, "BTCUSDT")

        assert removed == 2
        assert impl.has_any_klines(SPOT, "BTCUSDT") is False

    def test_clearing_leaves_other_symbols_alone(
        self, impl: IMarketDataRepository
    ) -> None:
        impl.save_klines(SPOT, [candle("BTCUSDT", 0), candle("ETHUSDT", 0)])

        impl.clear_klines(SPOT, "BTCUSDT")

        assert impl.has_any_klines(SPOT, "ETHUSDT") is True

    def test_clearing_one_market_leaves_the_other_market_alone(
        self, impl: IMarketDataRepository
    ) -> None:
        """`EPIC-027A`: clearing a Spot shard must never touch the Futures
        shard of the same symbol, and vice versa."""
        impl.save_klines(SPOT, [candle("BTCUSDT", 0)])
        impl.save_klines(FUTURES, [candle("BTCUSDT", 0)])

        impl.clear_klines(SPOT, "BTCUSDT")

        assert impl.has_any_klines(SPOT, "BTCUSDT") is False
        assert impl.has_any_klines(FUTURES, "BTCUSDT") is True

    def test_has_any_klines_is_true_for_data_in_any_interval(
        self, impl: IMarketDataRepository
    ) -> None:
        """Interval-agnostic on purpose (`BUG-078`): a caller deciding whether
        a symbol's storage is safe to delete must not read "empty" from the
        subset of intervals the UI happens to show."""
        impl.save_klines(SPOT, [candle(minutes=0, interval=TimeFrame.FOUR_HOURS)])

        assert impl.has_any_klines(SPOT, "BTCUSDT") is True
        assert impl.get_klines(SPOT, "BTCUSDT", MINUTE) == []

    def test_available_symbols_are_the_ones_holding_data(
        self, impl: IMarketDataRepository
    ) -> None:
        impl.save_klines(SPOT, [candle("ETHUSDT", 0), candle("BTCUSDT", 0)])

        assert impl.list_available_shards(SPOT) == ["BTCUSDT", "ETHUSDT"]

    def test_available_shards_are_scoped_to_one_market(
        self, impl: IMarketDataRepository
    ) -> None:
        impl.save_klines(SPOT, [candle("BTCUSDT", 0)])
        impl.save_klines(FUTURES, [candle("ETHUSDT", 0)])

        assert impl.list_available_shards(SPOT) == ["BTCUSDT"]
        assert impl.list_available_shards(FUTURES) == ["ETHUSDT"]
