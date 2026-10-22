"""`BOT-233` — the candles the workbench shows and syncs: one symbol on one venue, at one interval, over
one period. Both the stored-candles preview and a sync ask for exactly this.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_kind_backtester import (
    KindBacktestRequest,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    plan_market_of,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    MarketDataSyncRequest,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True, slots=True)
class CandleWindow:
    """What is drawn before a run and fetched by Sync candles, from the venue's own market (`BUG-172`)."""

    symbol: str
    venue: TradingVenue
    interval: TimeFrame
    start: datetime
    end: datetime


def window_of(request: KindBacktestRequest) -> CandleWindow:
    """The window a run was asked for."""
    return CandleWindow(
        request.symbol, request.venue, request.interval, request.start, request.end
    )


def sync_requests(window: CandleWindow) -> tuple[MarketDataSyncRequest, ...]:
    """What a sync fetches for `window`: its candles and the 1-second klines of its period (one request
    when the interval is 1s itself)."""
    return tuple(
        MarketDataSyncRequest(
            symbols=(window.symbol,),
            interval=interval,
            market=plan_market_of(window.venue),
            start_time=window.start,
            end_time=window.end,
        )
        for interval in dict.fromkeys((window.interval, TimeFrame.ONE_SECOND))
    )
