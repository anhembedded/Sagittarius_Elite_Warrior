"""`EPIC-040D` — what the Bots screen tells the Backtest workbench about the selection, and the
small pure helpers the presenter shares.

The selection is a bot's saved plan (never the Plan panel's unsaved edits, `EPIC-040C`), the planner's
market numbers for its symbol, and a position venue's risk facts once read.
"""

from __future__ import annotations

from dataclasses import dataclass

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
    venue_profile_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.funding_requirement import (
    FundingRequirement,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.sandbox_plan import (
    SandboxPlan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    PlanRiskFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.candle_window import (
    CandleWindow,
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


def request_of(
    world: WorkbenchSelection,
    plan: SandboxPlan,
    window: CandleWindow,
    funding: FundingRequirement,
) -> KindBacktestRequest | None:
    """The backtest the sandbox's plan asks for over `window`, judged by the sandbox's own bot's
    market numbers and risk facts (`world`); `None` while the numbers are still being read."""
    market, risk = world.market, world.risk
    if market is None or market.terms is None:
        return None
    return KindBacktestRequest(
        plan.symbol,
        plan.config,
        market.terms,
        window.interval,
        window.start,
        window.end,
        plan.venue,
        brackets=risk.brackets if risk is not None else None,
        funding=funding,
    )
