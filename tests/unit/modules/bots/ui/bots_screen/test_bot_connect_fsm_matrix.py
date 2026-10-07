"""`EPIC-034D` — the Connect step's own lifecycle."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_connect_fsm_matrix import (
    CONNECT_TRANSITIONS,
    ConnectEvent,
    ConnectState,
    next_state,
)

S = ConnectState
E = ConnectEvent


@pytest.mark.parametrize("state", list(S))
def test_selecting_a_bot_always_starts_a_read(state: ConnectState) -> None:
    assert next_state(state, E.SELECTED) is S.CONNECTING


@pytest.mark.parametrize("state", list(S))
def test_selecting_nothing_always_disconnects(state: ConnectState) -> None:
    assert next_state(state, E.DESELECTED) is S.NOT_CONNECTED


def test_only_a_read_that_succeeded_connects() -> None:
    reaching_connected = {
        (state, event)
        for (state, event), target in CONNECT_TRANSITIONS.items()
        if target is S.CONNECTED
    }

    assert reaching_connected == {
        (S.CONNECTING, E.READ_OK),
        (S.CONNECTED, E.READ_OK),
        (S.CONNECTED, E.REFRESH),
    }


def test_a_timer_re_read_never_locks_a_connected_chart_while_it_runs() -> None:
    assert next_state(S.CONNECTED, E.REFRESH) is S.CONNECTED


def test_a_failed_re_read_locks_it() -> None:
    assert next_state(S.CONNECTED, E.READ_FAILED) is S.FAILED


def test_a_failed_connection_retries_by_button_or_timer() -> None:
    assert next_state(S.FAILED, E.RETRY) is S.CONNECTING
    assert next_state(S.FAILED, E.REFRESH) is S.CONNECTING


def test_an_answer_with_nothing_asked_changes_nothing() -> None:
    assert next_state(S.NOT_CONNECTED, E.READ_OK) is S.NOT_CONNECTED
    assert next_state(S.FAILED, E.READ_OK) is S.FAILED
