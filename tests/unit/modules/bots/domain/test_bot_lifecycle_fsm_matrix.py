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
    PRICE_STALENESS_HALTS,
    PRICE_STREAM_STATES,
    RESUME_PROPOSES_STATES,
    BotLifecycleEvent,
    BotLifecycleState,
    BotLifecycleTarget,
    InvalidBotTransitionError,
    is_declared,
    may_hold_exposure,
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
    (S.STARTING, E.HALT): S.HALTED,
    (S.STARTING, E.HALT_TRANSIENT): S.AWAITING_RECOVERY,
    (S.STARTING, E.STOP): S.STOPPING,
    (S.STARTING, E.SWITCH_OFF): S.HALTED,
    (S.STARTING, E.FAULT): S.ERROR,
    (S.STARTING, E.APP_RESTART): S.HALTED,
    (S.STARTING, E.PRICE_OUTSIDE_RANGE): S.AWAITING_RANGE,
    (S.RUNNING, E.PAUSE): S.PAUSED,
    (S.RUNNING, E.STOP): S.STOPPING,
    (S.RUNNING, E.SWITCH_OFF): S.HALTED,
    (S.RUNNING, E.FAULT): S.ERROR,
    (S.RUNNING, E.HALT): S.HALTED,
    (S.RUNNING, E.HALT_TRANSIENT): S.AWAITING_RECOVERY,
    (S.RUNNING, E.APP_RESTART): S.RECOVERING,
    (S.PAUSED, E.RESUME): S.RUNNING,
    (S.PAUSED, E.STOP): S.STOPPING,
    (S.PAUSED, E.SWITCH_OFF): S.HALTED,
    (S.PAUSED, E.FAULT): S.ERROR,
    (S.PAUSED, E.HALT): S.HALTED,
    (S.PAUSED, E.APP_RESTART): S.RECOVERING,
    (S.RECOVERING, E.STOP): S.STOPPING,
    (S.RECOVERING, E.RESUME): S.RECOVERING,
    (S.RECOVERING, E.SWITCH_OFF): S.RECOVERING,
    (S.RECOVERING, E.RECONCILE_OK): T.PRIOR,
    (S.RECOVERING, E.RECONCILE_MISMATCH): S.HALTED,
    (S.RECOVERING, E.HALT): S.HALTED,
    (S.RECOVERING, E.FAULT): S.ERROR,
    (S.RECOVERING, E.APP_RESTART): S.RECOVERING,
    (S.HALTED, E.RESUME): S.STARTING,
    (S.HALTED, E.STOP): S.STOPPING,
    (S.HALTED, E.SWITCH_OFF): S.HALTED,
    (S.HALTED, E.FAULT): S.ERROR,
    (S.HALTED, E.APP_RESTART): S.HALTED,
    (S.AWAITING_RECOVERY, E.CONDITION_CLEARED): S.STARTING,
    (S.AWAITING_RECOVERY, E.RESUME): S.STARTING,
    (S.AWAITING_RECOVERY, E.BUDGET_EXHAUSTED): S.HALTED,
    (S.AWAITING_RECOVERY, E.HALT): S.HALTED,
    (S.AWAITING_RECOVERY, E.STOP): S.STOPPING,
    (S.AWAITING_RECOVERY, E.SWITCH_OFF): S.HALTED,
    (S.AWAITING_RECOVERY, E.FAULT): S.ERROR,
    (S.AWAITING_RECOVERY, E.APP_RESTART): S.HALTED,
    (S.AWAITING_RANGE, E.RANGE_ENTERED): S.STARTING,
    (S.AWAITING_RANGE, E.ENTRY_REFUSED): S.HALTED,
    (S.AWAITING_RANGE, E.STOP): S.STOPPING,
    (S.AWAITING_RANGE, E.HALT): S.HALTED,
    (S.AWAITING_RANGE, E.SWITCH_OFF): S.HALTED,
    (S.AWAITING_RANGE, E.FAULT): S.ERROR,
    (S.AWAITING_RANGE, E.APP_RESTART): S.RECOVERING,
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


@pytest.mark.parametrize("state", sorted(PRICE_STALENESS_HALTS))
def test_a_stale_price_feed_can_halt_every_state_that_holds_or_lays_orders(
    state: S,
) -> None:
    """`EPIC-035A` — `PRICE_FEED_STALE` is a `halt`, and each state that watches
    the price for staleness declares one."""
    assert next_target(state, E.HALT) is S.HALTED


def test_the_states_that_own_a_price_stream_are_exactly_the_ones_not_at_rest() -> None:
    assert frozenset(S) - {S.DRAFT, S.STOPPED} == PRICE_STREAM_STATES


def test_a_stopping_bot_is_not_halted_by_a_quiet_feed() -> None:
    """A stop sells at market and cancels; neither needs a tick, and halting it
    would turn the user's Stop into a resume that re-plans a ladder."""
    assert S.STOPPING in PRICE_STREAM_STATES
    assert S.STOPPING not in PRICE_STALENESS_HALTS


@pytest.mark.parametrize("state", [S.PAUSED, S.RECOVERING])
def test_a_paused_or_recovering_bot_never_halts_transiently(state: S) -> None:
    """ADR 042 D8: the owner's Pause is never undone by a machine, and a restart's closed
    order session cannot take the Resume path a recovery runs."""
    assert not is_declared(state, E.HALT_TRANSIENT)


def test_awaiting_recovery_is_left_by_a_person_a_stop_or_a_new_cause() -> None:
    """ADR 042 §2.1: every way out of the wait is declared, and none leads to RUNNING."""
    leaving = {
        event: next_target(S.AWAITING_RECOVERY, event)
        for event in E
        if is_declared(S.AWAITING_RECOVERY, event)
    }
    assert S.RUNNING not in leaving.values()
    assert leaving[E.STOP] is S.STOPPING
    assert leaving[E.APP_RESTART] is S.HALTED


def test_the_waiting_state_owns_a_price_stream_and_is_not_halted_again_by_a_quiet_feed() -> (
    None
):
    """The wait watches its exits, so it keeps the stream; a quiet feed is why it waits,
    so it must not halt it a second time."""
    assert S.AWAITING_RECOVERY in PRICE_STREAM_STATES
    assert S.AWAITING_RECOVERY not in PRICE_STALENESS_HALTS


def test_a_resume_re_plans_from_halted_and_from_the_wait_only() -> None:
    assert {S.HALTED, S.AWAITING_RECOVERY} == RESUME_PROPOSES_STATES
    assert all(is_declared(state, E.RESUME) for state in RESUME_PROPOSES_STATES)


def test_a_waiting_bot_is_active_and_has_no_pause_resume_edit_or_delete() -> None:
    """ADR 044 §2.1: it holds nothing to pause, and it is not at rest."""
    declared = {e for e in E if is_declared(S.AWAITING_RANGE, e)}

    assert declared.isdisjoint({E.PAUSE, E.RESUME, E.EDIT, E.DELETE, E.START})
    assert S.AWAITING_RANGE in PRICE_STREAM_STATES
    assert S.AWAITING_RANGE not in PRICE_STALENESS_HALTS


def test_a_waiting_bot_is_left_only_by_the_price_a_person_a_refusal_or_the_switch() -> (
    None
):
    """No way out lays a ladder except `range_entered`, which goes through STARTING."""
    leaving = {
        event: next_target(S.AWAITING_RANGE, event)
        for event in E
        if is_declared(S.AWAITING_RANGE, event)
    }

    assert S.RUNNING not in leaving.values()
    assert leaving[E.RANGE_ENTERED] is S.STARTING
    assert leaving[E.SWITCH_OFF] is S.HALTED, "an Emergency Stop ends the wait (D8)"
    assert leaving[E.APP_RESTART] is S.RECOVERING


@pytest.mark.parametrize("state", list(S))
def test_only_a_waiting_bot_and_one_recovering_into_the_wait_may_not_hold_exposure(
    state: S,
) -> None:
    """ADR 044 D2: the one fact every exposure watch asks, instead of naming states."""
    assert may_hold_exposure(state, None) is (state is not S.AWAITING_RANGE)
    assert may_hold_exposure(state, S.RUNNING) is (state is not S.AWAITING_RANGE)
    assert may_hold_exposure(state, S.AWAITING_RANGE) is (
        state not in {S.AWAITING_RANGE, S.RECOVERING}
    )
