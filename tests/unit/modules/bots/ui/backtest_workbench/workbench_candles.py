"""`EPIC-040F` — the candles the workbench's tests replay, and the sync that stores them.

One day of 15-minute candles swinging around 65,000 (`swinging_candles`), the period they cover and the
venue the bots of these tests trade on. `StoringSync` is the verified fake sync plus what a real sync
leaves behind: the 15-minute candles of the period, written to the repository. They were the Grid page's
builders before the page went (`EPIC-040A`).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    MarketDataSyncRequest,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_repository import (
    FakeMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sync import (
    FakeMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

SYMBOL = "BTCUSDT"
T0 = datetime(2026, 9, 1, tzinfo=UTC)
#: One day of 15-minute candles.
CANDLES = 96
PERIOD = (T0, T0 + timedelta(minutes=15 * CANDLES))

#: The bots of these tests trade on Spot Testnet; `BUG-172` reads its market.
VENUE = TradingVenue.SPOT_TESTNET


def swinging_candles() -> list[MarketData]:
    """BTC swinging ±2,600 around 65,000 every two hours: through four of the
    report's levels each way, inside its exits."""
    candles = []
    for index in range(CANDLES):
        o = 65000 + 2600 * math.sin(2 * math.pi * index / 8)
        c = 65000 + 2600 * math.sin(2 * math.pi * (index + 1) / 8)
        at = T0 + timedelta(minutes=15 * index)
        candles.append(
            MarketData(
                symbol=SYMBOL,
                interval=TimeFrame.FIFTEEN_MINUTES.value,
                open_time=at,
                open_price=round(o, 2),
                high_price=round(max(o, c) + 5, 2),
                low_price=round(min(o, c) - 5, 2),
                close_price=round(c, 2),
                volume=1.0,
                close_time=at + timedelta(minutes=15),
                quote_asset_volume=1.0,
                number_of_trades=1,
                taker_buy_base_asset_volume=0.5,
                taker_buy_quote_asset_volume=0.5,
            )
        )
    return candles


class StoringSync(FakeMarketDataSync):
    """The verified fake, plus what a real sync leaves behind: the 15-minute
    candles of the period, written to the repository."""

    def __init__(self, repository: FakeMarketDataRepository) -> None:
        super().__init__()
        self._repository = repository

    def sync(self, request: MarketDataSyncRequest) -> None:
        super().sync(request)
        if request.interval is TimeFrame.FIFTEEN_MINUTES:
            self._repository.save_klines(MarketType.SPOT, swinging_candles())
