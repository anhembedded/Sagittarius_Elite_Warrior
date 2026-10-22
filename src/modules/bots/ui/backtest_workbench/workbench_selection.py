"""`EPIC-040D` — what the Bots screen tells the Backtest workbench about the selection, and the
small pure helpers the presenter shares.

The selection is a bot's saved plan (never the Plan panel's unsaved edits, `EPIC-040C`), the planner's
market numbers for its symbol, and a position venue's risk facts once read.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market.result import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_kind_backtester import (
    KindBacktestRequest,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    plan_market_of,
    venue_profile_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    PlanRiskFacts,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    MarketDataSyncRequest,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True, slots=True)
class WorkbenchSelection:
    """The selected bot, as the workbench reads it."""

    bot: BotSnapshot | None = None
    market: PlannerMarket | None = None
    risk: PlanRiskFacts | None = None


def needs_brackets(venue: TradingVenue) -> bool:
    """A position venue's liquidation price needs the symbol's brackets (`EPIC-039J`)."""
    profile = venue_profile_of(venue)
    return profile is not None and bool(profile.margin_modes)


def sync_requests(request: KindBacktestRequest) -> tuple[MarketDataSyncRequest, ...]:
    """What a sync fetches for `request`: its candles and the 1-second klines of its period (one request
    when the interval is 1s itself)."""
    return tuple(
        MarketDataSyncRequest(
            symbols=(request.symbol,),
            interval=interval,
            market=plan_market_of(request.venue),
            start_time=request.start,
            end_time=request.end,
        )
        for interval in dict.fromkeys((request.interval, TimeFrame.ONE_SECOND))
    )
