"""The contract suite for `IStrategyChartOverlay` (HLD §10.3).

**Nothing to draw is an empty overlay, never an exception.** An unregistered
strategy key or no candles are both normal — a chart with nothing armed —
and the caller already treats "nothing to draw" as ordinary.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_chart_overlay import (
    IStrategyChartOverlay,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)


def _a_candle(index: int, close: float) -> MarketData:
    open_time = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(minutes=index)
    return MarketData(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_MINUTE.value,
        open_time=open_time,
        open_price=close,
        high_price=close,
        low_price=close,
        close_price=close,
        volume=1000.0,
        close_time=open_time + timedelta(minutes=1),
        quote_asset_volume=close * 1000.0,
        number_of_trades=10,
        taker_buy_base_asset_volume=500.0,
        taker_buy_quote_asset_volume=500.0 * close,
    )


class StrategyChartOverlayContract:
    """Inherit this, provide `impl` with `a_key` registered."""

    a_key = "ema_crossover"

    @pytest.fixture
    def impl(self) -> IStrategyChartOverlay:
        raise NotImplementedError(
            "a StrategyChartOverlayContract subclass must provide an `impl` "
            "fixture, with `a_key` registered"
        )

    def test_an_unregistered_key_draws_nothing_rather_than_raising(
        self, impl: IStrategyChartOverlay
    ) -> None:
        config = LiveStrategyConfig(
            strategy_key="no_such_strategy", symbol="BTCUSDT", interval="1m"
        )
        overlay = impl.overlay_for(config, [_a_candle(0, 100.0)])

        assert overlay.lines == ()
        assert overlay.zones == ()

    def test_no_candles_draws_nothing_rather_than_raising(
        self, impl: IStrategyChartOverlay
    ) -> None:
        config = LiveStrategyConfig(
            strategy_key=self.a_key, symbol="BTCUSDT", interval="1m"
        )
        overlay = impl.overlay_for(config, [])

        assert overlay.lines == ()
        assert overlay.zones == ()
