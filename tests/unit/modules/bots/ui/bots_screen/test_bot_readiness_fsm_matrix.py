"""`EPIC-034D`, `EPIC-034H` — a bot's readiness lifecycle: Connect, Design, Run."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_readiness_fsm_matrix import (
    CONNECTED_STATES,
    READINESS_TRANSITIONS,
    ReadinessEvent,
    ReadinessState,
    next_state,
)

S = ReadinessState
E = ReadinessEvent

_ASSESSMENTS = (E.DESIGN_OPEN, E.RUN_OPEN, E.ALL_CLEAR)


@pytest.mark.parametrize("state", list(S))
def test_selecting_a_bot_always_starts_a_read(state: ReadinessState) -> None:
    assert next_state(state, E.SELECTED) is S.CONNECTING


@pytest.mark.parametrize("state", list(S))
def test_selecting_nothing_always_disconnects(state: ReadinessState) -> None:
    assert next_state(state, E.DESELECTED) is S.NOT_CONNECTED


def test_only_a_read_that_succeeded_connects() -> None:
    reaching_connected = {
        (state, event)
        for (state, event), target in READINESS_TRANSITIONS.items()
        if target in CONNECTED_STATES and state not in CONNECTED_STATES
    }

    assert reaching_connected == {(S.CONNECTING, E.READ_OK)}


@pytest.mark.parametrize("state", CONNECTED_STATES)
def test_a_timer_re_read_never_locks_a_connected_chart_while_it_runs(
    state: ReadinessState,
) -> None:
    assert next_state(state, E.REFRESH) is state
    assert next_state(state, E.READ_OK) is state


@pytest.mark.parametrize("state", CONNECTED_STATES)
def test_a_failed_re_read_locks_it(state: ReadinessState) -> None:
    assert next_state(state, E.READ_FAILED) is S.FAILED


def test_a_failed_connection_retries_by_button_or_timer() -> None:
    assert next_state(S.FAILED, E.RETRY) is S.CONNECTING
    assert next_state(S.FAILED, E.REFRESH) is S.CONNECTING


@pytest.mark.parametrize("state", CONNECTED_STATES)
def test_retrying_a_connected_account_reads_it_again(state: ReadinessState) -> None:
    assert next_state(state, E.RETRY) is S.CONNECTING


def test_a_connected_account_is_judged_into_one_of_three_states() -> None:
    for state in CONNECTED_STATES:
        assert next_state(state, E.DESIGN_OPEN) is S.DESIGNING
        assert next_state(state, E.RUN_OPEN) is S.RUN_BLOCKED
        assert next_state(state, E.ALL_CLEAR) is S.READY


@pytest.mark.parametrize("state", [S.NOT_CONNECTED, S.CONNECTING, S.FAILED])
@pytest.mark.parametrize("event", _ASSESSMENTS)
def test_an_assessment_never_connects_an_account_that_is_not_read(
    state: ReadinessState, event: ReadinessEvent
) -> None:
    assert next_state(state, event) is state


def test_an_answer_with_nothing_asked_changes_nothing() -> None:
    assert next_state(S.NOT_CONNECTED, E.READ_OK) is S.NOT_CONNECTED
    assert next_state(S.FAILED, E.READ_OK) is S.FAILED


@pytest.mark.parametrize("event", list(E))
@pytest.mark.parametrize("state", list(S))
def test_every_pair_leads_to_a_declared_state(
    state: ReadinessState, event: ReadinessEvent
) -> None:
    assert next_state(state, event) in set(S)


def test_the_chart_and_the_plan_are_open_exactly_in_the_connected_states() -> None:
    assert set(CONNECTED_STATES) == {S.DESIGNING, S.RUN_BLOCKED, S.READY}
