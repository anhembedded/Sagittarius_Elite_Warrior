"""`BOT-235` - the Plan's rows for the loss at the stop loss and the gain at the take profit.

@details The owner's question on the Plan of a saved Futures draft (BNBUSDT, 730-750, 10 grids,
200 capital at 2x, stop 721, take profit 757): how much is lost if the stop hits, how much is made
if the price runs straight to the take profit. The numbers are the domain's
(`test_grid_exit_estimate.py` works them by hand); here the real `detail_for` is shown to carry
them to the rows, with the path and what is left out, and to give a bot at rest the guard's
liquidation estimate in place of "not in the bot's record".
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
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
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import GridKind
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_detail import (
    DetailInputs,
    detail_for,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_facts import BotFacts
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.exit_estimate_words import (
    LIQUIDATION_FIRST,
    rows_cut_by_liquidation,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_property_rows import (
    PROPERTY_KEYS,
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


def _bot(state: S = S.DRAFT, **changes: str) -> BotSnapshot:
    definition = BotDefinition(
        "bnb", "grid", TradingVenue.FUTURES_TESTNET, "BNBUSDT", {**_CONFIG, **changes}
    )
    return BotSnapshot.of(
        Bot(BotId("a00001"), definition, BotLifecycle(state, _NOW), _NOW), None
    )


def _facts(state: S = S.DRAFT, **changes: str):
    market = PlannerMarket(_TERMS, MarketView(D(740)), None, None)
    risk = PlanRiskFacts(
        FuturesSymbolSetting("BNBUSDT", 2, MarginType.ISOLATED, D(10**9)), BRACKETS
    )
    return detail_for(
        DetailInputs(
            _bot(state, **changes),
            GridKind(None, GridThresholds()),  # type: ignore[arg-type]
            market,
            _NOW,
            risk=risk,
        )
    ).facts


def test_the_rows_are_in_the_plan_and_the_facts_carry_a_text_for_each() -> None:
    assert {"loss_at_stop", "gain_at_take_profit"} <= set(PROPERTY_KEYS)
    assert {"loss_at_stop", "gain_at_take_profit"} <= set(BotFacts.__dataclass_fields__)


def test_the_owners_plan_says_the_loss_at_the_stop_with_its_path_and_what_it_leaves_out() -> (
    None
):
    """-8.2549 is 4.13% of the 200 (hand-worked in `test_grid_exit_estimate.py`)."""
    row = _facts().loss_at_stop

    assert "8.25" in row
    assert "-4.13% of capital" in row
    assert "falls from" in row
    assert "5 BUY orders" in row
    assert "a liquidation before the exit are left out" in row


def test_the_owners_plan_says_the_gain_at_the_take_profit() -> None:
    """+1.3887 is 0.69% of the 200: only the five SELLs fill, nothing is left to close."""
    row = _facts().gain_at_take_profit

    assert "1.39" in row
    assert "+0.69% of capital" in row
    assert "rises from" in row
    assert "5 SELL orders" in row
    assert "nothing is left to close" in row


def test_an_exit_that_is_off_has_no_row() -> None:
    facts = _facts(stop_loss="off")

    assert facts.loss_at_stop == ""
    assert facts.gain_at_take_profit != ""


def test_a_bot_with_a_run_shows_neither_estimate() -> None:
    """Its plan was drawn at the price its run began at, not at today's."""
    facts = _facts(S.RUNNING)

    assert (facts.loss_at_stop, facts.gain_at_take_profit) == ("", "")


def test_a_saved_bot_at_rest_shows_the_guards_liquidation_estimate() -> None:
    """The estimate `BUG-255` and `BOT-227` judge the stop against, the same one a design not
    saved yet shows (`BUG-261`), instead of "not in the bot's record"."""
    assert "liquidation near" in _facts().liquidation_estimate
    assert _facts(S.RUNNING).liquidation_estimate == ""


def test_a_stop_beyond_the_liquidation_price_says_the_margin_goes_first_not_a_loss() -> (
    None
):
    """Review of `BOT-235`: at 50x the long's liquidation estimate (about 723) is above the stop
    at 721, the guard refuses it as `STOP_LOSS_AFTER_LIQUIDATION`, and a loss "at the stop" would
    never happen: the row says so, and the take profit's figure is unaffected."""
    facts = _facts(leverage="50")

    assert facts.loss_at_stop == LIQUIDATION_FIRST
    assert facts.gain_at_take_profit != LIQUIDATION_FIRST
    assert "STOP_LOSS_AFTER_LIQUIDATION" not in facts.loss_at_stop


@pytest.mark.parametrize(
    ("direction", "side", "cut"),
    [
        (TradeDirection.LONG, "long", {"loss_at_stop"}),
        (TradeDirection.SHORT, "short", {"loss_at_stop"}),
        (TradeDirection.SHORT, "long", set()),
        (TradeDirection.NEUTRAL, "short", {"gain_at_take_profit"}),
        (TradeDirection.NEUTRAL, "long", {"loss_at_stop"}),
    ],
    ids=["long", "short", "short-wrong-leg", "neutral-short-leg", "neutral-long-leg"],
)
def test_the_side_the_guard_refused_decides_which_row_is_cut(
    direction: TradeDirection, side: str, cut: set[str]
) -> None:
    verdict = Verdict(
        VerdictSeverity.REFUSED, "STOP_LOSS_AFTER_LIQUIDATION", "x", subject=side
    )

    assert rows_cut_by_liquidation([verdict], direction) == cut
