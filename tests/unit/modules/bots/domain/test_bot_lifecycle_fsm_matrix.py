"""`EPIC-029B` — the lifecycle table is ADR §3.1, cell by cell, plus `EPIC-029E`'s `halt`.

`_EXPECTED` is typed from the ADR's table independently of the matrix, so a cell
changed in one and not the other fails here. Every undeclared pair is walked
too: a transition the ADR does not list must raise, naming the state and event.
"""

from __future__ import annotations

import itertools

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BOT_LIFECYCLE_TRANSITIONS,
    BotLifecycleEvent,
    BotLifecycleState,
    BotLifecycleTarget,
    InvalidBotTransitionError,
    is_declared,
    next_target,
)

S = BotLifecycleState
E = BotLifecycleEvent
T = BotLifecycleTarget

_EXPECTED: dict[tuple[S, E], S | T] = {
    (S.DRAFT, E.EDIT): S.DRAFT,
    (S.DRAFT, E.DELETE): T.REMOVED,
    (S.DRAFT, E.START): S.STARTING,
    (S.DRAFT, E.APP_RESTART): S.DRAFT,
    (S.STARTING, E.LADDER_READY): S.RUNNING,
    (S.STARTING, E.START_REFUSED): S.HALTED,
    (S.STARTING, E.STOP): S.STOPPING,
    (S.STARTING, E.SWITCH_OFF): S.HALTED,
    (S.STARTING, E.FAULT): S.ERROR,
    (S.STARTING, E.APP_RESTART): S.HALTED,
    (S.RUNNING, E.PAUSE): S.PAUSED,
    (S.RUNNING, E.STOP): S.STOPPING,
    (S.RUNNING, E.SWITCH_OFF): S.HALTED,
    (S.RUNNING, E.FAULT): S.ERROR,
    (S.RUNNING, E.HALT): S.HALTED,
    (S.RUNNING, E.APP_RESTART): S.RECOVERING,
    (S.PAUSED, E.RESUME): S.RUNNING,
    (S.PAUSED, E.STOP): S.STOPPING,
    (S.PAUSED, E.SWITCH_OFF): S.HALTED,
    (S.PAUSED, E.FAULT): S.ERROR,
    (S.PAUSED, E.HALT): S.HALTED,
    (S.PAUSED, E.APP_RESTART): S.RECOVERING,
    (S.RECOVERING, E.STOP): S.STOPPING,
    (S.RECOVERING, E.SWITCH_OFF): S.RECOVERING,
    (S.RECOVERING, E.RECONCILE_OK): T.PRIOR,
    (S.RECOVERING, E.RECONCILE_MISMATCH): S.HALTED,
    (S.RECOVERING, E.FAULT): S.ERROR,
    (S.RECOVERING, E.APP_RESTART): S.RECOVERING,
    (S.HALTED, E.RESUME): S.STARTING,
    (S.HALTED, E.STOP): S.STOPPING,
    (S.HALTED, E.SWITCH_OFF): S.HALTED,
    (S.HALTED, E.FAULT): S.ERROR,
    (S.HALTED, E.APP_RESTART): S.HALTED,
    (S.STOPPING, E.STOP): S.STOPPING,
    (S.STOPPING, E.STOP_CONFIRMED): S.STOPPED,
    (S.STOPPING, E.SWITCH_OFF): S.STOPPING,
    (S.STOPPING, E.FAULT): S.ERROR,
    (S.STOPPING, E.HALT): S.HALTED,
    (S.STOPPING, E.APP_RESTART): S.STOPPING,
    (S.STOPPED, E.EDIT): S.DRAFT,
    (S.STOPPED, E.DELETE): T.REMOVED,
    (S.STOPPED, E.START): S.STARTING,
    (S.STOPPED, E.APP_RESTART): S.STOPPED,
    (S.ERROR, E.STOP): S.STOPPING,
    (S.ERROR, E.SWITCH_OFF): S.ERROR,
    (S.ERROR, E.APP_RESTART): S.ERROR,
}

_UNDECLARED = [pair for pair in itertools.product(S, E) if pair not in _EXPECTED]


def test_the_matrix_declares_exactly_the_adr_table() -> None:
    assert BOT_LIFECYCLE_TRANSITIONS == _EXPECTED


@pytest.mark.parametrize(("pair", "target"), sorted(_EXPECTED.items()))
def test_every_declared_transition(pair: tuple[S, E], target: S | T) -> None:
    state, event = pair
    assert next_target(state, event) is target
    assert is_declared(state, event)


@pytest.mark.parametrize("pair", _UNDECLARED)
def test_every_undeclared_pair_raises_naming_state_and_event(
    pair: tuple[S, E],
) -> None:
    state, event = pair
    assert not is_declared(state, event)
    with pytest.raises(InvalidBotTransitionError) as caught:
        next_target(state, event)
    assert caught.value.state is state
    assert caught.value.event is event
    assert state.value in str(caught.value)
    assert event.value in str(caught.value)


@pytest.mark.parametrize("state", [s for s in S if s not in {S.DRAFT, S.STOPPED}])
def test_delete_is_declared_only_from_draft_and_stopped(state: S) -> None:
    with pytest.raises(InvalidBotTransitionError):
        next_target(state, E.DELETE)


def test_pause_while_starting_is_not_declared() -> None:
    """ADR §3.1: the UI disables it, and a call raises."""
    assert not is_declared(S.STARTING, E.PAUSE)


def test_stop_is_declared_in_stopping() -> None:
    """`EPIC-035C` (H5): a stop that waits can be asked for again."""
    assert is_declared(S.STOPPING, E.STOP)
    assert next_target(S.STOPPING, E.STOP) is S.STOPPING


def test_every_state_has_an_app_restart_cell() -> None:
    """ADR D12: a restart must have an answer for every saved state."""
    assert all(is_declared(state, E.APP_RESTART) for state in S)
