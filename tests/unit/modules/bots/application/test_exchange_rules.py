"""`BOT-174` — the readiness rules over the exchange's facts, as pure functions.

@details Numbers in, items and advisories out: no port, no clock, no screen. The
three states of the snapshot are told apart in one place (`judge_exchange`); the
rules see only a loaded one. Each boundary is tested at the value and one step
either side of it, so flipping an operator or shifting a threshold turns a test red.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services import (
    exchange_rules,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.exchange_rules import (
    CAPITAL_FIELD,
    CHECKING_THE_EXCHANGE,
    RULES,
    RuleContext,
    RuleOutcome,
    RunPurpose,
    field_verdicts,
    judge_exchange,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    ReadinessAdvisory,
    ReadinessFix,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeChecking,
    ExchangeUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_needs import (
    LadderNeeds,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.earlier_runs_inventory import (
    EarlierRunsInventory,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.exchange_facts_fixtures import (
    loaded,
)

START, RESUME = RunPurpose.START, RunPurpose.RESUME


def _needs(
    quote: str = "1000", base: str = "0", price: str = "100", capital: str = "1000"
) -> LadderNeeds:
    return LadderNeeds(Decimal(quote), Decimal(base), Decimal(price), Decimal(capital))


def _codes(outcome: RuleOutcome) -> list[str]:
    return [item.code for item in outcome.items]


# --- the snapshot's three states ----------------------------------------------


def test_a_snapshot_still_being_read_is_one_item_and_the_bot_is_not_ready() -> None:
    outcome = judge_exchange(ExchangeChecking(), _needs(), START)

    (item,) = outcome.items
    assert (item.code, item.reason, item.fix) == (
        "RUN_EXCHANGE_CHECKING",
        CHECKING_THE_EXCHANGE,
        ReadinessFix.WAIT,
    )
    assert item.refusal is BotRefusal.EXCHANGE_NOT_READ
    assert outcome.advisories == ()


def test_a_snapshot_that_could_not_be_read_names_why_and_offers_a_refresh() -> None:
    outcome = judge_exchange(ExchangeUnavailable("no API key"), _needs(), START)

    (item,) = outcome.items
    assert item.code == "RUN_EXCHANGE_UNAVAILABLE"
    assert "no API key" in item.reason
    assert item.fix is ReadinessFix.REFRESH_EXCHANGE


@pytest.mark.parametrize("purpose", [START, RESUME])
def test_neither_unread_state_is_read_as_an_empty_or_zero_account(
    purpose: RunPurpose,
) -> None:
    """An account with no quote would be `quote short`; an unread one is not that
    and never says it: the rules do not run, and the only finding is the state."""
    for unread in (ExchangeChecking(), ExchangeUnavailable("down")):
        outcome = judge_exchange(unread, _needs(base="5"), purpose)

        assert not {"RUN_QUOTE_SHORT", "RUN_BASE_SHORT"} & set(_codes(outcome))


def test_a_loaded_snapshot_with_enough_of_everything_leaves_nothing() -> None:
    assert judge_exchange(loaded(), _needs(), START) == RuleOutcome()
    assert judge_exchange(loaded(), _needs(base="0.4"), RESUME) == RuleOutcome()


def test_without_a_plan_only_the_snapshots_own_state_speaks() -> None:
    poor = loaded(quote_free=Decimal(1), base_free=Decimal(0))

    assert judge_exchange(poor, None, START) == RuleOutcome()
    assert judge_exchange(poor, None, RESUME) == RuleOutcome()


# --- rule 1: left from earlier runs (advisory, never blocks) -------------------


def test_a_base_an_earlier_run_kept_is_advised_with_its_value_and_never_blocks() -> (
    None
):
    earlier = EarlierRunsInventory(Decimal("0.0166"), Decimal("41.90"))
    outcome = judge_exchange(
        loaded(base_asset="ETH", earlier_runs=earlier), _needs(price="2500"), START
    )

    assert outcome.items == ()
    assert outcome.advisories == (
        ReadinessAdvisory(
            "EARLIER_RUNS_LEFT",
            "A previous run kept 0.0166 ETH ≈ 41.50 USDT that this run will not trade",
        ),
    )


def test_nothing_left_from_earlier_runs_is_not_mentioned() -> None:
    assert judge_exchange(loaded(), _needs(), START).advisories == ()


def test_what_earlier_runs_left_not_being_known_is_said_never_read_as_none() -> None:
    unknown = EarlierRunsInventory(unavailable="history unavailable")
    outcome = judge_exchange(loaded(earlier_runs=unknown), _needs(), START)

    (advisory,) = outcome.advisories
    assert advisory.code == "EARLIER_RUNS_UNKNOWN"
    assert "history unavailable" in advisory.text
    assert outcome.items == ()


def test_a_resume_continues_its_run_so_earlier_runs_are_not_its_business() -> None:
    earlier = EarlierRunsInventory(Decimal("0.0166"), Decimal("41.90"))

    assert (
        judge_exchange(loaded(earlier_runs=earlier), _needs(), RESUME).advisories == ()
    )


def test_the_value_falls_back_to_the_cost_when_no_plan_gives_a_price() -> None:
    earlier = EarlierRunsInventory(Decimal(2), Decimal("41.9"))
    outcome = judge_exchange(loaded(earlier_runs=earlier), None, START)

    assert "(cost 41.90 USDT)" in outcome.advisories[0].text


# --- rule 2: the free base against the SELLs a resume lays ---------------------


def test_a_resume_whose_sells_need_exactly_the_free_base_is_not_blocked() -> None:
    outcome = judge_exchange(
        loaded(base_free=Decimal("0.0028")), _needs(base="0.0028"), RESUME
    )

    assert outcome.items == ()


def test_a_resume_one_step_short_of_base_is_refused_naming_both_numbers() -> None:
    outcome = judge_exchange(
        loaded(base_asset="ETH", base_free=Decimal("0.00279999")),
        _needs(base="0.0028"),
        RESUME,
    )

    (item,) = outcome.items
    assert item.code == "RUN_BASE_SHORT"
    assert item.refusal is BotRefusal.BALANCE_TOO_SMALL
    assert "sells 0.0028 ETH" in item.reason
    assert "Spot Testnet has 0.00279999 ETH free" in item.reason


def test_the_base_locked_by_the_bots_own_sells_counts_because_the_resume_cancels_them() -> (
    None
):
    mine = loaded(
        base_free=Decimal("0.001"),
        base_locked=Decimal("0.002"),
        own_sell_base=Decimal("0.002"),
    )

    assert judge_exchange(mine, _needs(base="0.003"), RESUME).items == ()
    assert _codes(judge_exchange(mine, _needs(base="0.0031"), RESUME)) == [
        "RUN_BASE_SHORT"
    ]


def test_base_locked_by_orders_that_are_not_the_bots_is_named_as_the_cause() -> None:
    elsewhere = loaded(
        base_asset="ETH",
        base_free=Decimal("0.001"),
        base_locked=Decimal("0.005"),
        own_sell_base=Decimal("0.002"),
    )

    (item,) = judge_exchange(elsewhere, _needs(base="0.01"), RESUME).items

    assert "0.003 ETH is locked by orders that are not this bot's" in item.reason


def test_a_start_buys_its_own_base_so_a_poor_base_balance_never_blocks_it() -> None:
    assert (
        judge_exchange(loaded(base_free=Decimal(0)), _needs(base="5"), START).items
        == ()
    )


# --- rule 3: the free quote against the opening buy and the BUY levels ---------


def test_a_start_whose_ladder_costs_exactly_the_free_quote_is_not_blocked() -> None:
    outcome = judge_exchange(
        loaded(quote_free=Decimal(1000)), _needs(quote="1000"), START
    )

    assert outcome.items == ()


def test_a_start_one_cent_short_of_quote_is_refused_with_the_largest_capital_that_fits() -> (
    None
):
    outcome = judge_exchange(
        loaded(quote_free=Decimal("999.99")),
        _needs(quote="1000", capital="1100"),
        START,
    )

    (item,) = outcome.items
    assert item.code == "RUN_QUOTE_SHORT"
    assert item.refusal is BotRefusal.BALANCE_TOO_SMALL
    assert "need 1000.00 USDT" in item.reason
    assert "Spot Testnet has 999.99 USDT free" in item.reason
    # The needs scale with the capital: 1100 × 999.99 / 1000.
    assert "lower the capital to at most 1099.98" in item.reason
    assert (item.fix, item.target) == (ReadinessFix.EDIT_FIELD, CAPITAL_FIELD)


def test_the_need_is_rounded_up_and_the_balance_down_so_a_shortfall_is_never_hidden() -> (
    None
):
    (item,) = judge_exchange(
        loaded(quote_free=Decimal("100.001")), _needs(quote="100.009"), START
    ).items

    assert "need 100.01 USDT" in item.reason
    assert "has 100.00 USDT free" in item.reason


def test_a_resume_counts_the_quote_its_own_buys_lock_and_has_no_capital_to_edit() -> (
    None
):
    mine = loaded(
        quote_free=Decimal(300), quote_locked=Decimal(400), own_buy_quote=Decimal(400)
    )

    assert judge_exchange(mine, _needs(quote="700"), RESUME).items == ()
    (item,) = judge_exchange(mine, _needs(quote="700.01"), RESUME).items
    assert "resumed ladder's BUY levels need" in item.reason
    assert item.fix is ReadinessFix.NONE


def test_a_start_does_not_count_quote_locked_by_resting_orders_of_the_bot() -> None:
    mine = loaded(
        quote_free=Decimal(300), quote_locked=Decimal(400), own_buy_quote=Decimal(400)
    )

    assert _codes(judge_exchange(mine, _needs(quote="700"), START)) == [
        "RUN_QUOTE_SHORT"
    ]


def test_only_the_capital_item_speaks_on_the_capital_field() -> None:
    (item,) = judge_exchange(loaded(quote_free=Decimal(1)), _needs(), START).items

    (verdict,) = field_verdicts((item,))
    assert (verdict.code, verdict.reason, verdict.refuses) == (
        CAPITAL_FIELD,
        item.reason,
        True,
    )
    (resume_item,) = judge_exchange(
        loaded(quote_free=Decimal(1)), _needs(), RESUME
    ).items
    assert field_verdicts((resume_item,)) == ()


# --- the seam: the next rule is one function and one line ----------------------


def test_a_further_rule_is_one_more_function_in_the_registry(monkeypatch) -> None:
    def key_may_not_trade(context: RuleContext) -> RuleOutcome:
        return RuleOutcome(
            advisories=(
                ReadinessAdvisory("KEY", f"can trade: {context.facts.can_trade}"),
            )
        )

    monkeypatch.setattr(exchange_rules, "RULES", (*RULES, key_may_not_trade))

    outcome = judge_exchange(loaded(can_trade=False), _needs(), START)

    assert ReadinessAdvisory("KEY", "can trade: False") in outcome.advisories
