"""`EPIC-040C` — a sandbox is judged by the symbol's rules, never by the account.

@details The kind's own `validate` judges, over the real `GridKind`: a plan the exchange would refuse
(a level below the minimum notional, a tick-misaligned price) is still refused, and what needs the
account says it was not checked in a simulation. The domain verdicts themselves are not changed."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.sandbox_plan import (
    SandboxPlan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    PlanRiskFacts,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.futures_replay_builders import (
    BRACKETS,
    position_config,
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


def _futures_plan(direction: str = "SHORT", leverage: int = 3) -> SandboxPlan:
    config = position_config(direction, leverage, stop_loss="percent:5")
    return SandboxPlan.from_bot(bot(config=config, venue=TradingVenue.FUTURES_TESTNET))


def test_the_venues_limits_decide_what_a_sandbox_may_try() -> None:
    """A short at leverage 3 is the venue's to allow: Spot refuses it, a Futures venue does not."""
    config = position_config("SHORT", 3, stop_loss="percent:5")
    on_spot = SandboxPlan.from_bot(bot(config=config, venue=TradingVenue.SPOT_TESTNET))

    on_futures = _futures_plan()

    spot_codes = {v.code for v in judge_sandbox(_KIND, on_spot, market()).verdicts}
    futures_codes = {
        v.code for v in judge_sandbox(_KIND, on_futures, market()).verdicts
    }
    assert "DIRECTION_NOT_ALLOWED" in spot_codes
    assert "DIRECTION_NOT_ALLOWED" not in futures_codes
    assert "LEVERAGE_NOT_ALLOWED" not in futures_codes


def test_the_symbols_risk_facts_reach_the_liquidation_verdicts() -> None:
    risk = PlanRiskFacts(
        FuturesSymbolSetting("BTCUSDT", 3, MarginType.ISOLATED, Decimal(10**9)),
        BRACKETS,
    )

    judged = judge_sandbox(_KIND, _futures_plan(), market(), risk)

    codes = {v.code for v in judged.verdicts}
    assert "LIQUIDATION_ESTIMATE" in codes
    assert "LIQUIDATION_FACTS_NOT_READ" not in codes


def test_a_position_venue_without_risk_facts_says_liquidation_was_not_judged() -> None:
    judged = judge_sandbox(_KIND, _futures_plan(), market(), None)

    codes = {v.code: v for v in judged.verdicts}
    assert "LIQUIDATION_ESTIMATE" not in codes
    assert not codes["LIQUIDATION_FACTS_NOT_READ"].refuses
    assert "not judged" in codes["LIQUIDATION_FACTS_NOT_READ"].reason


def test_spot_has_no_liquidation_to_judge_and_says_nothing_about_it() -> None:
    judged = judge_sandbox(_KIND, SandboxPlan.from_bot(bot()), market())

    assert "LIQUIDATION_FACTS_NOT_READ" not in {v.code for v in judged.verdicts}
