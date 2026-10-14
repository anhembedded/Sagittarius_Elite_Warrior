"""`BUG-209` — a bot that stops trading is never only an INFO line.

An unattended run is judged by grepping the journal for WARNING, ERROR and CRITICAL
(`LOGGING.md` §3). Every lifecycle transition used to log at INFO, so a bot that went to
HALTED or ERROR left nothing for that grep to find. `BotRunState.transition` is the one
place a transition is applied, so the level is decided there: HALTED is a WARNING, ERROR is
an ERROR, and the table itself is the list this guard walks - a new row into either state is
covered the day it is added.
"""

from __future__ import annotations

import logging

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle import (
    bot_run_state,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_run_state import (
    BotRunState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BOT_LIFECYCLE_TRANSITIONS,
    BotLifecycleEvent,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    GridRuntime,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    grid_world,
)

S = BotLifecycleState
E = BotLifecycleEvent
LOGGER = "App.Bots.GridExecutor"

#: Rows of the table that land in a state a person must be told about, with the level.
_INTO_HALTED_OR_ERROR = [
    (state, event, target)
    for (state, event), target in BOT_LIFECYCLE_TRANSITIONS.items()
    if target in (S.HALTED, S.ERROR)
]
_LEVEL = {S.HALTED: logging.WARNING, S.ERROR: logging.ERROR}


def _run_state_in(state: S) -> BotRunState:
    world = grid_world(state=state)
    stored = world.store.load(BotId(BOT))
    return BotRunState(stored.bot, GridRuntime(levels=()), world.store, world.clock)


def _records_of_transition(
    caplog: pytest.LogCaptureFixture, state: S, event: E
) -> list[logging.LogRecord]:
    run_state = _run_state_in(state)
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        run_state.transition(event, GridReason.ORDER_REFUSED, "the gate said no")
    return [r for r in caplog.records if r.name == LOGGER]


def _transitions_that_stay_silent_below_their_level(
    caplog: pytest.LogCaptureFixture,
) -> list[str]:
    """Every table row into HALTED or ERROR whose record is below its level."""
    quiet = []
    for state, event, target in _INTO_HALTED_OR_ERROR:
        records = _records_of_transition(caplog, state, event)
        if not any(r.levelno >= _LEVEL[target] for r in records):
            quiet.append(f"{state.value} --{event.value}--> {target.value}")
    return quiet


def test_the_table_has_rows_into_both_halted_and_error() -> None:
    targets = {target for _, _, target in _INTO_HALTED_OR_ERROR}

    assert targets == {S.HALTED, S.ERROR}, "the guard below would walk nothing"


@pytest.mark.parametrize(
    ("state", "event", "target"),
    _INTO_HALTED_OR_ERROR,
    ids=lambda v: getattr(v, "value", str(v)),
)
def test_every_transition_into_halted_or_error_logs_at_its_level(
    caplog: pytest.LogCaptureFixture, state: S, event: E, target: S
) -> None:
    records = _records_of_transition(caplog, state, event)

    assert [r.levelno for r in records] == [_LEVEL[target]], (
        "exactly one record, at the level of the state the bot landed in"
    )
    assert "the gate said no" in records[0].getMessage(), "the reason is in the line"
    assert "order_refused" in records[0].getMessage()


def test_the_guard_finds_a_transition_that_logs_below_its_level(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The probe that breaks it: the pre-fix behaviour, every transition at INFO."""
    assert _transitions_that_stay_silent_below_their_level(caplog) == []

    monkeypatch.setattr(bot_run_state, "landing_level", lambda _state: logging.INFO)

    quiet = _transitions_that_stay_silent_below_their_level(caplog)
    assert len(quiet) == len(_INTO_HALTED_OR_ERROR)
    assert "RUNNING --halt--> HALTED" in quiet


@pytest.mark.parametrize(
    ("state", "event"),
    [
        (S.DRAFT, E.START),
        (S.STARTING, E.LADDER_READY),
        (S.RUNNING, E.PAUSE),
        (S.RUNNING, E.STOP),
        (S.RUNNING, E.APP_RESTART),
        (S.HALTED, E.STOP),
    ],
)
def test_a_transition_into_any_other_state_stays_at_info(
    caplog: pytest.LogCaptureFixture, state: S, event: E
) -> None:
    records = _records_of_transition(caplog, state, event)

    assert [r.levelno for r in records] == [logging.INFO]


def test_an_event_the_table_does_not_declare_is_a_warning_and_keeps_the_reason(
    caplog: pytest.LogCaptureFixture,
) -> None:
    run_state = _run_state_in(S.ERROR)
    assert not run_state.can(E.HALT)

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        run_state.apply_or_record(E.HALT, GridReason.ORDER_REFUSED, "min notional")

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1, "one refusal, one WARNING"
    assert "[bot-transition-refused]" in warnings[0].getMessage()
    assert "ERROR" in warnings[0].getMessage(), "it names where the bot stayed"
    assert run_state.state is S.ERROR
    assert run_state.runtime.reason is GridReason.ORDER_REFUSED
    assert run_state.runtime.reason_detail == "min notional"


def test_a_declared_event_through_apply_or_record_is_the_transition_not_a_second_line(
    caplog: pytest.LogCaptureFixture,
) -> None:
    run_state = _run_state_in(S.RUNNING)

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        run_state.apply_or_record(E.HALT, GridReason.RATE_LIMITED, "slow down")

    assert [r.levelno for r in caplog.records if r.name == LOGGER] == [logging.WARNING]
    assert run_state.state is S.HALTED
