"""Builders for the sandbox tests (`EPIC-040C`): a stopped bot's saved plan, and the market it is
judged against."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    MarketView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import (
    GRID_KIND_ID,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    CONFIG,
    TERMS,
)

SAVED = dict(CONFIG)


def bot(
    bot_id: str = "a3f9c1",
    config: dict[str, str] | None = None,
    venue: TradingVenue = TradingVenue.SPOT_TESTNET,
) -> BotSnapshot:
    return BotSnapshot(
        bot_id=bot_id,
        name=f"bot {bot_id}",
        kind=GRID_KIND_ID,
        venue=venue,
        symbol="BTCUSDT",
        state=BotLifecycleState.STOPPED,
        created_at=datetime(2026, 9, 1, tzinfo=UTC),
        run_started_at=None,
        config=SAVED if config is None else config,
    )


def market(foreign_open_orders: int | None = 3) -> PlannerMarket:
    return PlannerMarket(
        terms=TERMS,
        market=MarketView(Decimal(65000), foreign_open_orders=foreign_open_orders),
        atr_range=None,
        bollinger=None,
    )
