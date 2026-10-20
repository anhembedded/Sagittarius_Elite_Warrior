"""`EPIC-040D` — the line under the banner: whose plan the sandbox copies and whose fees a run charges."""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market.result import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.sandbox_plan import (
    SandboxPlan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench import (
    workbench_words as words,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import write_value
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind


def source_text(plan: SandboxPlan | None, market: PlannerMarket | None) -> str:
    if plan is None:
        return ""
    text = (
        f"A sandbox of bot {plan.source_bot_id} ({plan.symbol}, "
        f"{plan.venue.display_name}): edit freely, it is not the bot's plan."
    )
    if market is None or market.terms is None:
        return text
    return f"{text} {words.fees_line(_percent(market.terms.maker_fee), _percent(market.terms.taker_fee))}"


def _percent(fraction: Decimal) -> str:
    """A fee rate as the person reads it: 0.001 is 0.10%."""
    return write_value(ColumnKind.PERCENT, fraction * 100)
