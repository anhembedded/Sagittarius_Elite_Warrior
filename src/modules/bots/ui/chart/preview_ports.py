"""Offline ports for the bots previews: sample candles and a calling thread.

The bot chart's preview and the Grid backtest's preview are built on the same
candles, BTC swinging between the report example's levels (60,000–70,000),
so neither opens a socket nor starts a pool.
"""

from __future__ import annotations

import concurrent.futures
import math
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import Any

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.support.charting.contracts.i_candle_feed import (
    CandleStreamStart,
    ICandleFeed,
    OlderCandlesRequest,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

#: How many candles the sample feed serves at most.
SAMPLE_CANDLES = 120


def sample_candle(
    symbol: str, interval: TimeFrame, start: datetime, index: int
) -> MarketData:
    """@brief The `index`-th sample candle after `start`, `interval` long."""
    length = timedelta(seconds=interval.to_seconds())
    mid = 65000 + 3500 * math.sin(index / 9) + 600 * math.sin(index / 2.3)
    open_price = mid - 150 * math.cos(index)
    close_price = mid + 150 * math.cos(index)
    return MarketData(
        symbol=symbol,
        interval=interval.value,
        open_time=start + length * index,
        open_price=open_price,
        high_price=max(open_price, close_price) + 220,
        low_price=min(open_price, close_price) - 220,
        close_price=close_price,
        volume=40 + 15 * abs(math.sin(index)),
        close_time=start + length * (index + 1),
        quote_asset_volume=0.0,
        number_of_trades=0,
        taker_buy_base_asset_volume=0.0,
        taker_buy_quote_asset_volume=0.0,
    )


class SampleCandleFeed(ICandleFeed):
    """@brief Serves the sample candles from `start`; never syncs or streams."""

    def __init__(self, start: datetime, interval: TimeFrame) -> None:
        self._start = start
        self._interval = interval

    def sync(
        self,
        symbol: str,
        interval: TimeFrame,
        cancelled: Callable[[], bool],
        *,
        newest: int | None = None,
    ) -> None:
        return None

    def load_history(
        self, symbol: str, interval: TimeFrame, limit: int
    ) -> Sequence[MarketData]:
        return tuple(
            sample_candle(symbol, self._interval, self._start, index)
            for index in range(min(limit, SAMPLE_CANDLES))
        )

    def load_older(
        self, request: OlderCandlesRequest, cancelled: Callable[[], bool]
    ) -> Sequence[MarketData]:
        return ()

    def start_stream(
        self, owner_id: str, symbol: str, interval: TimeFrame
    ) -> CandleStreamStart:
        return CandleStreamStart(False, "The preview does not stream.")

    def stop_stream(self, owner_id: str) -> None:
        return None


class CallingThread(IThreadManager):
    """@brief Runs each task at once, on the caller's thread: a preview has
    nothing to wait for and nothing to shut down."""

    def submit(
        self, task: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> concurrent.futures.Future[Any]:
        future: concurrent.futures.Future[Any] = concurrent.futures.Future()
        future.set_result(task(*args, **kwargs))
        return future

    def shutdown(self, wait: bool = True) -> None:
        return None
