"""`EPIC-039H` - the plan is judged on the setting the venue will have, so the screen and Start agree.

@details The settings gate (`EPIC-039E`) makes a symbol's leverage and margin mode the grid's own at
Start, before the first order. A plan judged on the account's *current* setting therefore told a
user whose symbol sits on Cross that the grid was refused, while Start would have made it isolated
and gone on. One function (`intended_setting`) builds the setting the plan is judged on, in the
one place both the screen's judgement and the plan-time guard of Start read it from.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
    ExposureLimits,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
    PlanRiskFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_grid_checks import (
    judge_futures_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_plan_risk_inputs import (
    PlanRiskInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    evaluate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    FuturesGridThresholds,
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.intended_setting import (
    intended_setting,
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
_LIMITS = ExposureLimits(frozenset(TradeDirection), 20, ExposureKind.POSITION)
_CROSS_AT_ONE = FuturesSymbolSetting("BTCUSDT", 1, MarginType.CROSSED, D(250_000))
_ISOLATED_AT_ONE = replace(_CROSS_AT_ONE, margin_type=MarginType.ISOLATED)


def _screen_inputs(setting: FuturesSymbolSetting) -> BotKindInputs:
    base = inputs(direction="LONG", leverage="3")
    return BotKindInputs(
        base.config,
        base.terms,
        base.market,
        base.account,
        _LIMITS,
        PlanRiskFacts(setting, _BRACKETS),
    )


def test_a_symbol_on_cross_is_not_refused_for_what_the_gate_will_set_right() -> None:
    evaluation = evaluate_grid(_screen_inputs(_CROSS_AT_ONE), GridThresholds())

    assert "CROSS_MARGIN_UNSUPPORTED" not in {v.code for v in evaluation.verdicts}


def test_the_account_setting_the_plan_is_read_with_changes_no_verdict() -> None:
    on_cross = evaluate_grid(_screen_inputs(_CROSS_AT_ONE), GridThresholds())
    on_isolated = evaluate_grid(_screen_inputs(_ISOLATED_AT_ONE), GridThresholds())
    other_leverage = evaluate_grid(
        _screen_inputs(replace(_CROSS_AT_ONE, leverage=20)), GridThresholds()
    )

    assert on_cross.verdicts == on_isolated.verdicts == other_leverage.verdicts


def test_the_screen_and_start_give_a_cross_account_the_same_verdicts() -> None:
    """Start asks the plan-time guard after the gate made the symbol the grid's own."""
    screen = evaluate_grid(_screen_inputs(_CROSS_AT_ONE), GridThresholds())
    assert screen.params is not None and screen.plan is not None
    after_the_gate = intended_setting(_CROSS_AT_ONE, screen.params, _BRACKETS)
    market = _screen_inputs(_CROSS_AT_ONE).market

    at_start = judge_futures_plan(
        PlanRiskInputs(
            screen.params,
            screen.plan,
            after_the_gate,
            _BRACKETS,
            market.last_price,
            FuturesGridThresholds(),
            market.daily_atr,
        )
    )

    futures_codes = {v.code for v in at_start}
    assert futures_codes, "the guard judged something"
    on_the_screen = [v for v in screen.verdicts if v.code in futures_codes]
    assert [v.code for v in on_the_screen] == [v.code for v in at_start]
    assert [v.reason for v in on_the_screen] == [v.reason for v in at_start]


def test_the_intended_setting_is_isolated_at_the_grids_own_leverage() -> None:
    params = evaluate_grid(_screen_inputs(_CROSS_AT_ONE), GridThresholds()).params
    assert params is not None

    setting = intended_setting(_CROSS_AT_ONE, params, _BRACKETS)

    assert setting.margin_type is MarginType.ISOLATED
    assert setting.leverage == params.leverage == 3
    assert setting.symbol == "BTCUSDT"
    assert setting.max_notional == D(250_000)
