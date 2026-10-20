"""`EPIC-040C` — a sandbox is judged by the symbol's rules, never by the account.

@details The kind's own `validate` judges, over the real `GridKind`: a plan the exchange would refuse
(a level below the minimum notional, a tick-misaligned price) is still refused, and what needs the
account says it was not checked in a simulation. The domain verdicts themselves are not changed."""

from __future__ import annotations

from dataclasses import replace

from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.sandbox_plan import (
    SandboxPlan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import GridKind
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import any_refused
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest.sandbox_judge import (
    judge_sandbox,
    sandbox_line,
)

from .sandbox_fixtures import SAVED, bot, market

_KIND = GridKind(None, GridThresholds())  # type: ignore[arg-type]


def _codes(plan: SandboxPlan, **world: object) -> dict[str, object]:
    judged = judge_sandbox(_KIND, plan, market(**world))  # type: ignore[arg-type]
    return {v.code: v for v in judged.verdicts}


def test_a_sandbox_of_the_saved_plan_is_judged_and_drawn() -> None:
    judged = judge_sandbox(_KIND, SandboxPlan.from_bot(bot()), market())

    assert judged.verdicts and not any_refused(judged.verdicts)
    assert judged.overlay is not None


def test_the_symbols_rules_still_refuse_a_bad_plan() -> None:
    """Minimum notional is the symbol's rule: capital too small for ten levels is refused."""
    plan = SandboxPlan.from_bot(bot()).with_config({**SAVED, "capital_quote": "20"})

    judged = judge_sandbox(_KIND, plan, market())

    assert any_refused(judged.verdicts)


def test_the_key_check_did_not_run_and_the_tab_says_so_in_a_simulation() -> None:
    verdicts = _codes(SandboxPlan.from_bot(bot()))

    verdict = verdicts["KEY_NOT_READ"]
    assert not verdict.refuses  # type: ignore[attr-defined]
    line = sandbox_line(verdict)  # type: ignore[arg-type]
    assert "Not checked in a simulation" in line
    assert "key's permission to trade" in line
    assert "did not run" not in line and "was not read" not in line
    # the domain's own verdict is not worded by the tab
    assert "was not read" in verdict.reason  # type: ignore[attr-defined]


def test_the_real_accounts_open_orders_are_not_judged() -> None:
    """The planner market carries the account's open orders; a sandbox leaves them out."""
    verdicts = _codes(SandboxPlan.from_bot(bot()), foreign_open_orders=7)

    assert "FOREIGN_ORDERS_NOT_READ" in verdicts
    assert (
        "not checked in a simulation"
        in sandbox_line(
            verdicts["FOREIGN_ORDERS_NOT_READ"]  # type: ignore[arg-type]
        ).lower()
    )
    assert "NO_FOREIGN_ORDERS" not in verdicts


def test_other_verdicts_are_worded_as_the_planner_words_them() -> None:
    verdicts = _codes(SandboxPlan.from_bot(bot()))

    other = next(
        v
        for c, v in verdicts.items()
        if c not in ("KEY_NOT_READ", "FOREIGN_ORDERS_NOT_READ")
    )
    assert "Not checked in a simulation" not in sandbox_line(other)  # type: ignore[arg-type]


def test_a_plan_without_market_numbers_has_no_verdicts() -> None:
    judged = judge_sandbox(_KIND, SandboxPlan.from_bot(bot()), None)

    assert judged.verdicts == ()
    assert replace(judged).overlay is None
