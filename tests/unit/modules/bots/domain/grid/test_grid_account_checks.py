"""`EPIC-034F` — the account's constraints at and around each boundary: the
balance the capital must fit, the base the plan buys first (ADR O2), the key's
permission to trade."""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    AccountView,
    BotKindInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    GridEvaluation,
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
    inputs,
)

CENT = Decimal("0.01")
TITLE = "Spot Testnet"


def account(available: str = "10000", *, can_trade: bool | None = True) -> AccountView:
    return AccountView(Decimal(available), "USDT", can_trade, TITLE)


def _evaluate(view: AccountView | None, **changes: str) -> GridEvaluation:
    base = inputs(**changes)
    return evaluate_grid(
        BotKindInputs(base.config, base.terms, base.market, view), GridThresholds()
    )


def _verdict(evaluation: GridEvaluation, *codes: str) -> Verdict:
    matches = [v for v in evaluation.verdicts if v.code in codes]
    assert len(matches) == 1, evaluation.verdicts
    return matches[0]


# --- the base for the sell levels: the plan buys it first (ADR O2) ----------


def test_the_sell_levels_base_is_bought_first_so_the_account_needs_none() -> None:
    evaluation = _evaluate(account("10000"))
    verdict = _verdict(evaluation, "OPENING_BUY", "NO_OPENING_BUY")
    assert verdict.code == "OPENING_BUY"
    assert verdict.severity is VerdictSeverity.OK
    plan = evaluation.plan
    assert plan is not None
    assert verdict.numbers["opening_base"] == plan.opening_buy_quantity
    assert verdict.numbers["opening_quote"] == (
        plan.opening_buy_quantity * plan.last_price
    )
    assert "needs no base of its own" in verdict.reason


def test_holding_no_base_never_blocks_a_plan_with_sell_levels() -> None:
    """The account view carries no base at all: the plan must not need any."""
    evaluation = _evaluate(account("10000"))
    assert not any(v.refuses for v in evaluation.verdicts)


def test_a_plan_below_the_price_buys_nothing_first() -> None:
    evaluation = _evaluate(
        account("10000"), lower="50000", upper="60000", take_profit="off"
    )
    verdict = _verdict(evaluation, "OPENING_BUY", "NO_OPENING_BUY")
    assert verdict.code == "NO_OPENING_BUY"


# --- the key may trade -------------------------------------------------------


@pytest.mark.parametrize(
    ("can_trade", "code", "refuses"),
    [
        (True, "KEY_CAN_TRADE", False),
        (False, "KEY_CANNOT_TRADE", True),
        (None, "KEY_PERMISSION_UNKNOWN", False),
    ],
)
def test_the_key_flag(can_trade: bool | None, code: str, refuses: bool) -> None:
    verdict = _verdict(
        _evaluate(account(can_trade=can_trade)),
        "KEY_CAN_TRADE",
        "KEY_CANNOT_TRADE",
        "KEY_PERMISSION_UNKNOWN",
        "KEY_NOT_READ",
    )
    assert verdict.code == code
    assert verdict.refuses is refuses


def test_a_key_that_cannot_trade_names_the_venue_and_where_to_fix_it() -> None:
    verdict = _verdict(_evaluate(account(can_trade=False)), "KEY_CANNOT_TRADE")
    assert TITLE in verdict.reason
    assert "Tools → Options → Trading" in verdict.reason


def test_without_the_account_the_key_check_says_it_did_not_run() -> None:
    verdict = _verdict(_evaluate(None), "KEY_NOT_READ")
    assert verdict.severity is VerdictSeverity.OK


def test_a_negative_balance_is_not_a_balance() -> None:
    with pytest.raises(ValueError, match="negative"):
        AccountView(Decimal(-1), "USDT", True, TITLE)
