"""`EPIC-029` ADR D15 — market_data's own ports as a live chart's candle feed.

@details `LiveChartCoordinator` lives in support and reads its candles through
support's `ICandleFeed`. The three ports it needs (`IMarketDataSync`,
`IHistoricalKlines`, `IMarketStream`) are this context's, so the adapter is
published here, once, beside them: a trading desk and a bot's chart both
build it from the ports they already receive, and neither keeps a copy
(a departure from the ADR's "each module's `ui/`", for that reason).

It is bound to one market at construction: a feed is the market its chart
shows (`EPIC-028C`: a Futures desk charts Futures candles).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
    MarketDataSyncRequest,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    IMarketStream,
)
from Sagittarius_Elite_Warrior.src.support.charting.contracts.i_candle_feed import (
    CandleStreamStart,
    ICandleFeed,
    OlderCandlesRequest,
)


class MarketDataCandleFeed(ICandleFeed):
    """One market's candles, from the market-data ports."""

    def __init__(
        self,
        sync: IMarketDataSync,
        history: IHistoricalKlines,
        stream: IMarketStream,
        market: MarketType,
    ) -> None:
        self._sync = sync
        self._history = history
        self._stream = stream
        self._market = market

    def sync(
        self, symbol: str, interval: TimeFrame, cancelled: Callable[[], bool]
    ) -> None:
        self._sync.sync(
            MarketDataSyncRequest(
                symbols=(symbol,),
                interval=interval,
                market=self._market,
                cancellation_requested=cancelled,
            )
        )

    def load_history(
        self, symbol: str, interval: TimeFrame, limit: int
    ) -> Sequence[MarketData]:
        # `newest_first=True` is how a limit keeps the most RECENT candles;
        # a chart draws chronologically, so they are reversed here.
        newest_first = self._history.load(
            self._market, symbol, interval, limit=limit, newest_first=True
        )
        return tuple(reversed(newest_first))

    def load_older(
        self, request: OlderCandlesRequest, cancelled: Callable[[], bool]
    ) -> Sequence[MarketData]:
        stored = self._stored_before(request)
        if len(stored) >= request.limit:
            return stored
        # The store is short of a window: ask this feed's own market for the
        # span right before the oldest candle drawn (an upsert, so candles
        # already stored are written again, never twice), then read it back,
        # so what is drawn is what a restart reads.
        span = timedelta(seconds=request.interval.to_seconds() * request.limit)
        self._sync.sync(
            MarketDataSyncRequest(
                symbols=(request.symbol,),
                interval=request.interval,
                market=self._market,
                start_time=request.before - span,
                end_time=request.before,
                cancellation_requested=cancelled,
            )
        )
        return self._stored_before(request)

    def _stored_before(self, request: OlderCandlesRequest) -> Sequence[MarketData]:
        # The store bounds a read by `open_time`, both ends inclusive, so one
        # row more than wanted is read and the one that opens at `before`
        # (the oldest candle drawn) is dropped: no gap, no candle twice.
        newest_first = self._history.load(
            self._market,
            request.symbol,
            request.interval,
            limit=request.limit + 1,
            end_time=request.before,
            newest_first=True,
        )
        older = [row for row in newest_first if row.open_time < request.before]
        return tuple(reversed(older[: request.limit]))

    def start_stream(
        self, owner_id: str, symbol: str, interval: TimeFrame
    ) -> CandleStreamStart:
        outcome = self._stream.start(owner_id, self._market, [symbol], interval)
        return CandleStreamStart(outcome.success, outcome.message)

    def stop_stream(self, owner_id: str) -> None:
        # The outcome is ignored: `success=False` means this owner held no
        # stream, the ordinary case for an unconditional stop.
        self._stream.stop(owner_id)
