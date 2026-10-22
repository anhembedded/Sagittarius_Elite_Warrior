"""`BOT-233` — the candles the workbench shows and syncs: one symbol on one venue, at one interval, over
one period. Both the stored-candles preview and a sync ask for exactly this.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

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

#: The longest period Sync candles also fetches 1-second klines for (`BOT-232`, review finding 4; the
#: owner's delegate, 2026-10-22). A week is the workbench's default period and 604,800 rows, which
#: the real store takes in minutes (`test_grid_backtest_stored_klines.py`); a year at 1d would be
#: about 31.5M. Past it the replay runs coarse, which it already supports and labels
#: (`coarse_periods`), and says so in words.
FINE_KLINES_MAX_PERIOD = timedelta(days=7)


@dataclass(frozen=True, slots=True)
class CandleWindow:
    """What is drawn before a run and fetched by Sync candles, from the venue's own market (`BUG-172`)."""

    symbol: str
    venue: TradingVenue
    interval: TimeFrame
    start: datetime
    end: datetime

    @property
    def has_fine_klines_synced(self) -> bool:
        """Whether Sync candles fetches this period's 1-second klines (not past `FINE_KLINES_MAX_PERIOD`)."""
        return self.end - self.start <= FINE_KLINES_MAX_PERIOD


def window_of(request: KindBacktestRequest) -> CandleWindow:
    """The window a run was asked for."""
    return CandleWindow(
        request.symbol, request.venue, request.interval, request.start, request.end
    )


def sync_requests(window: CandleWindow) -> tuple[MarketDataSyncRequest, ...]:
    """What a sync fetches for `window`: its candles and, for a period within `FINE_KLINES_MAX_PERIOD`,
    the 1-second klines of its period (one request when the interval is 1s itself)."""
    intervals = (window.interval, TimeFrame.ONE_SECOND)
    wanted = intervals if window.has_fine_klines_synced else intervals[:1]
    return tuple(
        MarketDataSyncRequest(
            symbols=(window.symbol,),
            interval=interval,
            market=plan_market_of(window.venue),
            start_time=window.start,
            end_time=window.end,
        )
        for interval in dict.fromkeys(wanted)
    )
