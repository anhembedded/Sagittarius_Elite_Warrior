"""`EPIC-034H` — what is left before a bot starts, judged by the one function
the screen and Start both call: each step's items, status and words."""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness_assessment import (
    MARKET_NOT_READ,
    ConnectionRead,
    ConnectionState,
    ReadinessInputs,
    RunFacts,
    assess_readiness,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    ReadinessFix,
    ReadinessStep,
    StepStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    AccountView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import GridKind
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    CONFIG,
    TERMS,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    inputs as grid_inputs,
)

TITLE = "Spot Testnet"
_KIND = GridKind(None, GridThresholds())  # type: ignore[arg-type]
_MARKET = PlannerMarket(TERMS, grid_inputs().market, None, None)
_ACCOUNT = AccountView(Decimal(50_000), "USDT", True, TITLE)
CONNECTED = ConnectionRead(ConnectionState.CONNECTED, TITLE, _ACCOUNT)
_NO_FACTS = RunFacts()


def _assess(
    connection: ConnectionRead = CONNECTED,
    market: PlannerMarket | None = _MARKET,
    run: RunFacts = _NO_FACTS,
    config: dict[str, str] | None = None,
):
    return assess_readiness(
        ReadinessInputs(
            kind=_KIND,
            kind_id="grid",
            symbol="BTCUSDT",
            config=config or dict(CONFIG),
            connection=connection,
            market=market,
            run=run,
        )
    )


def _status(readiness, step: ReadinessStep) -> StepStatus:
    return readiness.step(step).status


def test_a_connected_account_and_a_sound_plan_leave_nothing() -> None:
    readiness = _assess()

    assert readiness.can_start
    assert readiness.things_left == 0
    assert [s.status for s in readiness.steps] == [StepStatus.DONE] * 3
    assert readiness.summary == "Ready to start"


def test_the_three_steps_come_in_order() -> None:
    assert [s.step for s in _assess().steps] == [
        ReadinessStep.CONNECT,
        ReadinessStep.DESIGN,
        ReadinessStep.RUN,
    ]


# --- Connect -----------------------------------------------------------------


def test_an_account_being_read_is_one_item_to_wait_for_and_design_waits() -> None:
    readiness = _assess(ConnectionRead(ConnectionState.READING, TITLE), market=None)

    (item,) = readiness.items
    assert (item.step, item.fix, item.refusal) == (
        ReadinessStep.CONNECT,
        ReadinessFix.WAIT,
        BotRefusal.VENUE_NOT_READY,
    )
    assert item.reason == f"{TITLE}: Reading the account…"
    assert _status(readiness, ReadinessStep.DESIGN) is StepStatus.WAITING
    assert _status(readiness, ReadinessStep.RUN) is StepStatus.WAITING


def test_a_failed_read_names_the_venue_says_why_and_offers_retry() -> None:
    failed = ConnectionRead(
        ConnectionState.FAILED, TITLE, reason="The exchange could not be reached."
    )

    readiness = _assess(failed)

    (item,) = readiness.items
    assert item.reason == f"{TITLE}: The exchange could not be reached."
    assert item.fix is ReadinessFix.RETRY_CONNECTION
    assert "spot_testnet" not in item.reason
    assert _status(readiness, ReadinessStep.CONNECT) is StepStatus.OPEN


def test_nothing_of_design_is_judged_while_the_account_is_unread() -> None:
    """A plan judged against an account that was not read is a guess (D1): the
    design's own refusals do not appear until Connect is done."""
    bad_plan = {**CONFIG, "capital_quote": "1"}

    readiness = _assess(ConnectionRead(ConnectionState.READING, TITLE), config=bad_plan)

    assert readiness.step(ReadinessStep.DESIGN).items == ()


# --- Design ------------------------------------------------------------------


def test_each_blocking_constraint_is_an_item_naming_its_code_and_field() -> None:
    readiness = _assess(config={**CONFIG, "capital_quote": "1"})

    items = readiness.step(ReadinessStep.DESIGN).items
    assert [i.code for i in items] == ["LEVEL_BELOW_MIN_NOTIONAL"]
    assert items[0].fix is ReadinessFix.EDIT_FIELD
    assert items[0].target == "LEVEL_BELOW_MIN_NOTIONAL"
    assert items[0].refusal is BotRefusal.PARAMETERS_REFUSED
    assert "about" in items[0].reason  # the capital that clears it


def test_advice_is_never_an_item() -> None:
    """A range far outside the ATR advises and leaves Start open."""
    market = PlannerMarket(TERMS, grid_inputs(daily_atr=Decimal(1)).market, None, None)

    readiness = _assess(market=market)

    assert readiness.can_start


def test_the_balance_and_the_key_are_design_items_read_from_the_account() -> None:
    poor = ConnectionRead(
        ConnectionState.CONNECTED, TITLE, AccountView(Decimal(1), "USDT", False, TITLE)
    )

    readiness = _assess(poor)

    assert {i.code for i in readiness.step(ReadinessStep.DESIGN).items} == {
        "CAPITAL_ABOVE_BALANCE",
        "KEY_CANNOT_TRADE",
    }


def test_market_numbers_not_read_yet_is_a_design_item_to_wait_for() -> None:
    readiness = _assess(market=None)

    (item,) = readiness.items
    assert (item.code, item.reason, item.fix) == (
        "DESIGN_MARKET_READING",
        MARKET_NOT_READ,
        ReadinessFix.WAIT,
    )


def test_a_market_that_could_not_be_read_says_why_and_cannot_be_fixed_here() -> None:
    readiness = _assess(market=PlannerMarket(None, None, None, None, "no book"))

    (item,) = readiness.items
    assert item.reason == "The plan cannot be judged: no book"
    assert item.fix is ReadinessFix.NONE


def test_a_kind_nobody_knows_is_one_design_item() -> None:
    readiness = assess_readiness(
        ReadinessInputs(
            kind=None,
            kind_id="dca",
            symbol="BTCUSDT",
            config={},
            connection=CONNECTED,
            market=_MARKET,
            run=RunFacts(),
        )
    )

    (item,) = readiness.items
    assert item.reason == "No kind of bot is called 'dca'."


# --- Run ---------------------------------------------------------------------


def test_another_active_bot_is_an_item_whose_fix_is_to_stop_it() -> None:
    readiness = _assess(run=RunFacts(other_active_bot="aaa111"))

    (item,) = readiness.items
    assert item.step is ReadinessStep.RUN
    assert item.reason == "Bot aaa111 is still active; stop it before starting another"
    assert (item.fix, item.target) == (ReadinessFix.STOP_OTHER_BOT, "aaa111")
    assert item.refusal is BotRefusal.ONE_RUNNING_BOT_DURING_FAST_TRACK


def test_a_symbol_held_by_another_owner_is_an_item() -> None:
    (item,) = _assess(run=RunFacts(lease_holder="strategy.x")).items

    assert item.reason == "BTCUSDT is held by another owner"
    assert item.refusal is BotRefusal.SYMBOL_LEASED


def test_a_budget_over_trading_caps_is_an_item_fixed_in_the_grid_count() -> None:
    (item,) = _assess(run=RunFacts(budget_problem="too many orders")).items

    assert item.refusal is BotRefusal.BUDGET_REFUSED
    assert item.fix is ReadinessFix.EDIT_FIELD
    assert item.target == "TOO_MANY_LEVELS"


def test_a_venue_that_cannot_run_a_spot_grid_is_named_once_and_design_waits() -> None:
    run = RunFacts(
        venue_problem="Futures Testnet is not a Spot venue this app trades on"
    )

    readiness = _assess(run=run)

    assert [i.code for i in readiness.items] == ["RUN_VENUE_NOT_READY"]
    assert _status(readiness, ReadinessStep.DESIGN) is StepStatus.WAITING


def test_an_unreachable_venue_is_not_said_twice() -> None:
    """Connect already says it; the Run step's venue item would count one
    cause as two things left."""
    failed = ConnectionRead(ConnectionState.FAILED, TITLE, reason="no key")

    readiness = _assess(failed, run=RunFacts(venue_problem="not enabled"))

    assert [i.code for i in readiness.items] == ["CONNECT_FAILED"]


# --- counting and words ------------------------------------------------------


def test_every_item_across_the_steps_is_counted_and_worded() -> None:
    readiness = _assess(
        config={**CONFIG, "capital_quote": "1"},
        run=RunFacts(other_active_bot="aaa111", lease_holder="x"),
    )

    assert readiness.things_left == 3
    assert readiness.summary == "3 things left"
    assert not readiness.can_start
    assert readiness.message().startswith("3 things left: ")
    assert "Bot aaa111 is still active" in readiness.message()
    assert [s.status for s in readiness.steps] == [
        StepStatus.DONE,
        StepStatus.OPEN,
        StepStatus.OPEN,
    ]


def test_one_thing_left_is_singular() -> None:
    assert _assess(run=RunFacts(lease_holder="x")).summary == "1 thing left"


@pytest.mark.parametrize("left", [1, 2])
def test_run_waits_only_while_an_earlier_step_has_items_and_run_has_none(
    left: int,
) -> None:
    connection = (
        ConnectionRead(ConnectionState.READING, TITLE) if left == 1 else CONNECTED
    )
    config = CONFIG if left == 1 else {**CONFIG, "capital_quote": "1"}

    readiness = _assess(
        connection, market=None if left == 1 else _MARKET, config=config
    )

    assert _status(readiness, ReadinessStep.RUN) is StepStatus.WAITING
