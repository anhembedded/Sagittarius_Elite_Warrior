"""`EPIC-039J` - a plan on a position venue is judged for liquidation by the same evaluation
the Start and the screen share, once the symbol's risk facts are read.

@details The business promise: with the facts, a Futures plan's verdicts include the guard's
(`LIQUIDATION_ESTIMATE` per exposed side, each saying which side); without them, or on Spot,
the verdicts are exactly the ones the plan earned before this epic."""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureLimits,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
    PlanRiskFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    evaluate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBracket,
    LeverageBrackets,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    inputs,
)

D = Decimal
_BRACKETS = LeverageBrackets(
    "BTCUSDT",
    (
        LeverageBracket(1, 125, D(0), D(50_000), D("0.004"), D(0)),
        LeverageBracket(2, 100, D(50_000), D(250_000), D("0.005"), D(50)),
    ),
)
_FACTS = PlanRiskFacts(
    FuturesSymbolSetting("BTCUSDT", 3, MarginType.ISOLATED, D(10**9)), _BRACKETS
)
_LIMITS = ExposureLimits(frozenset(TradeDirection), 20)


def _futures(direction: str, risk: PlanRiskFacts | None) -> BotKindInputs:
    base = inputs(direction=direction, leverage="3")
    return BotKindInputs(
        base.config, base.terms, base.market, base.account, _LIMITS, risk
    )


def _estimates(verdicts) -> dict[str, object]:
    return {v.subject: v for v in verdicts if v.code == "LIQUIDATION_ESTIMATE"}


def test_a_long_plan_with_facts_earns_one_estimate_that_says_it_is_the_long() -> None:
    evaluation = evaluate_grid(_futures("LONG", _FACTS), GridThresholds())
    assert set(_estimates(evaluation.verdicts)) == {"long"}


def test_a_neutral_plan_with_facts_earns_an_estimate_for_each_side() -> None:
    evaluation = evaluate_grid(_futures("NEUTRAL", _FACTS), GridThresholds())
    assert set(_estimates(evaluation.verdicts)) == {"long", "short"}


def test_without_the_facts_no_liquidation_is_judged() -> None:
    with_facts = evaluate_grid(_futures("LONG", _FACTS), GridThresholds())
    without = evaluate_grid(_futures("LONG", None), GridThresholds())
    assert not _estimates(without.verdicts)
    assert without.verdicts == tuple(
        v for v in with_facts.verdicts if v in without.verdicts
    )


def test_a_spot_plan_earns_no_liquidation_verdict() -> None:
    evaluation = evaluate_grid(inputs(), GridThresholds())
    assert not _estimates(evaluation.verdicts)
    assert all(v.subject == "" for v in evaluation.verdicts)
