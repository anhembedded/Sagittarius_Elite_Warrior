"""`EPIC-046B` - the Plan of a Grid with a trigger price, through the real `detail_for`.

Two of the owner's questions of 2026-10-22, on the Live tab's chart and Plan rows:

  * the chart draws the trigger line while the plan can still enter, and leaves it out once the
    bot has laid its ladder (the wiring of `plan_trigger_line.shown_for`);
  * the Loss-at-stop and Result-at-TP rows start from the trigger, where the bot will enter, not
    from today's price (`entry_plan` at `entry_price`, ADR 046 D5).

The plan is `BOT-235`'s BNBUSDT Futures draft, 730-750, 10 grids, with a trigger at 735 and the
market at 745, above it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import (
    Bot,
    BotDefinition,
    BotLifecycle,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
    MarketView,
    PlanRiskFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import OverlayRole
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import GridKind
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_detail import (
    BotDetail,
    DetailInputs,
    detail_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.futures_world import (
    BRACKETS,
)

D = Decimal
_NOW = datetime(2026, 10, 22, 9, tzinfo=UTC)
_TERMS = ExchangeTerms(
    tick_size=D("0.01"),
    step_size=D("0.01"),
    min_notional=D(5),
    maker_fee=D("0.0002"),
    taker_fee=D("0.0004"),
    max_notional_per_order=D(100_000),
    max_open_orders=200,
)
_CONFIG = {
    "lower": "730",
    "upper": "750",
    "grid_count": "10",
    "spacing": "ARITHMETIC",
    "capital_quote": "200",
    "stop_loss": "price:721",
    "take_profit": "price:757",
    "direction": "LONG",
    "leverage": "2",
}


def _detail(state: S = S.DRAFT, market_price: str = "745", **changes: str) -> BotDetail:
    definition = BotDefinition(
        "bnb", "grid", TradingVenue.FUTURES_TESTNET, "BNBUSDT", {**_CONFIG, **changes}
    )
    bot = BotSnapshot.of(
        Bot(BotId("a00001"), definition, BotLifecycle(state, _NOW), _NOW), None
    )
    risk = PlanRiskFacts(
        FuturesSymbolSetting("BNBUSDT", 2, MarginType.ISOLATED, D(10**9)), BRACKETS
    )
    return detail_for(
        DetailInputs(
            bot,
            GridKind(None, GridThresholds()),  # type: ignore[arg-type]
            PlannerMarket(_TERMS, MarketView(D(market_price)), None, None),
            _NOW,
            risk=risk,
        )
    )


def _trigger_lines(detail: BotDetail) -> list[str]:
    assert detail.overlay is not None
    return [
        line.label for line in detail.overlay.lines if line.role is OverlayRole.TRIGGER
    ]


def test_a_draft_with_a_trigger_draws_its_line_on_the_chart() -> None:
    assert _trigger_lines(_detail(trigger_price="735")) == ["Trigger ≤ 735"]


def test_a_running_bot_draws_no_trigger_line() -> None:
    """The real `detail_for`: it latched, so the line is left out (red without `shown_for`)."""
    assert _trigger_lines(_detail(S.RUNNING, trigger_price="735")) == []


def test_the_estimates_of_a_triggered_plan_start_from_the_trigger() -> None:
    """With the market at 745 and the trigger at 735, the rows equal those of the same plan
    without a trigger and the market at 735: the bot will enter at the trigger."""
    triggered = _detail(trigger_price="735").facts
    at_the_trigger = _detail(market_price="735").facts

    assert "falls from 735" in triggered.loss_at_stop
    assert triggered.loss_at_stop == at_the_trigger.loss_at_stop
    assert triggered.gain_at_take_profit == at_the_trigger.gain_at_take_profit
    assert triggered.loss_at_stop != _detail().facts.loss_at_stop, (
        "without the trigger the plan starts from 745"
    )
