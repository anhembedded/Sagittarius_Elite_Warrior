"""What deleting removes, and what it must leave alone.

One of the three parts of `IMarketDataRepository`'s contract suite — see
`contract_market_data_repository.py`. `BUG-078` is the reason
`has_any_klines()` is pinned here: a caller deciding whether a symbol's
storage is safe to delete must not judge "empty" against only the intervals
the UI happens to show.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    MINUTE,
    candle,
)


class MarketDataDeletionContract:
    """Part of `MarketDataRepositoryContract`; see that class. A subclass
    supplies the `impl` fixture."""

    # -- deleting ------------------------------------------------------------

    def test_clearing_one_interval_leaves_the_others(
        self, impl: IMarketDataRepository
    ) -> None:
        impl.save_klines(
            [candle(minutes=0), candle(minutes=0, interval=TimeFrame.FIVE_MINUTES)]
        )

        removed = impl.clear_klines("BTCUSDT", MINUTE)

        assert removed == 1
        assert impl.get_klines("BTCUSDT", MINUTE) == []
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
        assert impl.get_klines("BTCUSDT", MINUTE) == []

    def test_available_symbols_are_the_ones_holding_data(
        self, impl: IMarketDataRepository
    ) -> None:
        impl.save_klines([candle("ETHUSDT", 0), candle("BTCUSDT", 0)])

        assert impl.list_available_shards() == ["BTCUSDT", "ETHUSDT"]
