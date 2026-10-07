"""`EPIC-034F`, decision D7 — every constraint is named, and each violation
blocks exactly when the decision says it does.

The table (`GRID_CONSTRAINTS`) declares, per constraint, the violation codes it
can answer and whether each blocks. These tests provoke every code and compare
what the verdict really does (`REFUSED` blocks, `WARNING` advises) with the
declaration, so a check cannot start refusing for strategy judgement, nor
stop refusing for money, without the table and the decision changing with it.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    AccountView,
    BotKindInputs,
    PriceBand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_check_inputs import (
    GridCheckInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_constraints import (
    GRID_CONSTRAINTS,
    run_checks,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    evaluate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    TERMS,
    inputs,
)

_ACCOUNT = AccountView(Decimal(10000), "USDT", True, "Spot Testnet")
_THIN = {
    "last_price": Decimal("100.1"),
    "lower": "100",
    "upper": "100.2",
    "grid_count": "1",
    "capital_quote": "1000",
    "stop_loss": "off",
    "take_profit": "off",
}


def _judge(
    account: AccountView | None = _ACCOUNT, **kwargs: object
) -> tuple[Verdict, ...]:
    base = inputs(**kwargs)
    return evaluate_grid(
        BotKindInputs(base.config, base.terms, base.market, account), GridThresholds()
    ).verdicts


#: One plan that provokes each violation code.
_PROVOKING: dict[str, dict[str, object]] = {
    "EVERY_CYCLE_LOSES": _THIN,
    "SOME_GRIDS_LOSE": {
        "terms": replace(TERMS, max_open_orders=1000),
        "last_price": Decimal(150),
        "lower": "100",
        "upper": "200",
        "grid_count": "400",
        "capital_quote": "400000",
        "stop_loss": "off",
        "take_profit": "off",
    },
    "LEVEL_BELOW_MIN_NOTIONAL": {"terms": replace(TERMS, min_notional=Decimal(10**9))},
    "LEVEL_ABOVE_MAX_NOTIONAL": {
        "terms": replace(TERMS, max_notional_per_order=Decimal(1))
    },
    "TOO_MANY_LEVELS": {"grid_count": "101"},
    "LEVEL_OUTSIDE_PRICE_BAND": {
        "terms": replace(
            TERMS,
            price_band=PriceBand(
                Decimal("0.95"), Decimal("1.05"), Decimal("0.95"), Decimal("1.05")
            ),
        )
    },
    "CAPITAL_ABOVE_BALANCE": {"account": AccountView(Decimal(1), "USDT", True, "x")},
    "KEY_CANNOT_TRADE": {"account": AccountView(Decimal(10000), "USDT", False, "x")},
    "STEP_BELOW_MINIMUM": {"grid_count": "100", "capital_quote": "10000"},
    "RANGE_OUTSIDE_ATR_BAND": {"daily_atr": Decimal(1)},
    "STOP_LOSS_INSIDE_RANGE": {"stop_loss": "price:60000"},
    "STOP_LOSS_DISTANCE": {"stop_loss": "percent:10"},
    "TAKE_PROFIT_INSIDE_RANGE": {"take_profit": "price:70000"},
    "TAKE_PROFIT_DISTANCE": {"take_profit": "percent:10"},
    "ARITHMETIC_ON_WIDE_RANGE": {
        "upper": "90000",
        "terms": replace(TERMS, max_notional_per_order=Decimal(10**6)),
    },
}


def _declared() -> dict[str, bool]:
    return {
        code: blocks
        for constraint in GRID_CONSTRAINTS
        for code, blocks in constraint.violations.items()
    }


def test_every_declared_violation_has_a_plan_that_provokes_it() -> None:
    assert set(_PROVOKING) == set(_declared())


@pytest.mark.parametrize("code", sorted(_PROVOKING))
def test_a_violation_blocks_exactly_when_the_decision_says(code: str) -> None:
    kwargs = dict(_PROVOKING[code])
    account = kwargs.pop("account", _ACCOUNT)
    assert account is None or isinstance(account, AccountView)
    verdicts = _judge(account, **kwargs)
    verdict = next((v for v in verdicts if v.code == code), None)
    assert verdict is not None, [v.code for v in verdicts]
    expected = VerdictSeverity.REFUSED if _declared()[code] else VerdictSeverity.WARNING
    assert verdict.severity is expected


def test_no_constraint_names_the_same_code_twice() -> None:
    codes = [code for c in GRID_CONSTRAINTS for code in c.violations]
    assert len(codes) == len(set(codes))


def test_constraint_names_are_unique_and_each_is_a_sentence_of_words() -> None:
    names = [constraint.name for constraint in GRID_CONSTRAINTS]
    assert len(names) == len(set(names))
    assert all(name.replace("_", "").isalpha() and name.islower() for name in names)


def test_the_rules_of_the_exchange_and_money_block() -> None:
    blocking = {code for code, blocks in _declared().items() if blocks}
    assert blocking == {
        "EVERY_CYCLE_LOSES",
        "LEVEL_BELOW_MIN_NOTIONAL",
        "LEVEL_ABOVE_MAX_NOTIONAL",
        "TOO_MANY_LEVELS",
        "LEVEL_OUTSIDE_PRICE_BAND",
        "CAPITAL_ABOVE_BALANCE",
        "KEY_CANNOT_TRADE",
        "STOP_LOSS_INSIDE_RANGE",
        "TAKE_PROFIT_INSIDE_RANGE",
    }


def test_advice_never_blocks() -> None:
    advisory = {code for code, blocks in _declared().items() if not blocks}
    assert advisory == {
        "SOME_GRIDS_LOSE",
        "STEP_BELOW_MINIMUM",
        "RANGE_OUTSIDE_ATR_BAND",
        "STOP_LOSS_DISTANCE",
        "TAKE_PROFIT_DISTANCE",
        "ARITHMETIC_ON_WIDE_RANGE",
    }


def test_run_checks_answers_one_verdict_per_constraint_in_the_tables_order() -> None:
    evaluation = evaluate_grid(inputs(), GridThresholds())
    assert evaluation.plan is not None and evaluation.derived is not None
    assert evaluation.params is not None
    check_inputs = GridCheckInputs(
        evaluation.params,
        evaluation.plan,
        evaluation.derived,
        TERMS,
        inputs().market,
        GridThresholds(),
    )
    verdicts = run_checks(check_inputs)
    assert verdicts == tuple(c.check(check_inputs) for c in GRID_CONSTRAINTS)
    assert verdicts == evaluation.verdicts
