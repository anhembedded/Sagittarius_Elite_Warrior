"""A fake exchange behind `IMarketDataSync` (`BUG-178`): what a sync asks of
the exchange is stored, as the sync handler stores what the exchange sent."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
    MarketDataSyncRequest,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)


class FakeExchangeSync(IMarketDataSync):
    """An exchange with `listed` candles: a sync stores those that open inside
    the span it asks for, as the sync handler writes what the exchange sent."""

    def __init__(
        self, store: FakeHistoricalKlines, listed: list[MarketData], market: MarketType
    ) -> None:
        self._store, self._listed, self._market = store, listed, market
        self.requests: list[MarketDataSyncRequest] = []

    def sync(self, request: MarketDataSyncRequest) -> None:
        self.requests.append(request)
        start, end = request.start_time, request.end_time
        assert start is not None and end is not None, "a backfill names its span"
        self._store.seed(
            [k for k in self._listed if start <= k.open_time <= end], self._market
        )
