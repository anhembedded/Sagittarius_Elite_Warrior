"""`EPIC-029F` — a bot's buttons follow its lifecycle table, and say why not."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
    StartConditions,
    availability,
    export_plan_availability,
)

S = BotLifecycleState
A = BotAction

#: The ADR's table, read once more by hand: what a user may do in each state.
LEGAL = {
    S.DRAFT: {A.START, A.SAVE, A.DELETE},
    S.STARTING: {A.STOP},
    S.RUNNING: {A.PAUSE, A.STOP},
    S.PAUSED: {A.RESUME, A.STOP},
    S.RECOVERING: {A.RESUME, A.STOP},
    S.HALTED: {A.RESUME, A.CONFIRM_RESUME, A.STOP},
    S.STOPPING: {A.STOP},
    S.STOPPED: {A.START, A.SAVE, A.DELETE},
    S.ERROR: {A.STOP},
}


@pytest.mark.parametrize("state", list(S), ids=lambda s: s.value)
def test_exactly_the_legal_actions_are_live(state: BotLifecycleState) -> None:
    live = {action for action in A if availability(state, action).enabled}
    assert live == LEGAL[state]


@pytest.mark.parametrize("state", list(S), ids=lambda s: s.value)
def test_every_disabled_action_names_the_state_that_blocks_it(
    state: BotLifecycleState,
) -> None:
    for action in set(A) - LEGAL[state]:
        reason = availability(state, action).reason
        assert state.value.lower() in reason, (action, reason)


def test_what_is_left_blocks_start_and_is_its_reason() -> None:
    """`EPIC-034H`: the readiness's words are Start's reason, whole."""
    blocked = availability(
        S.DRAFT, A.START, StartConditions(blocked_by="2 things left: a; b")
    )

    assert (blocked.enabled, blocked.reason) == (False, "2 things left: a; b")


def test_start_with_nothing_left_says_it_saves_first() -> None:
    """Unsaved edits are not a thing left: Save and start saves them (D8)."""
    ready = availability(S.DRAFT, A.START)

    assert ready.enabled
    assert "Save the changed parameters" in ready.reason


def test_a_refusal_never_blocks_an_action_other_than_start() -> None:
    refused = StartConditions(blocked_by="1 thing left: x")

    assert availability(S.DRAFT, A.SAVE, refused).enabled
    assert availability(S.RUNNING, A.STOP, refused).enabled


def test_export_plan_is_live_exactly_while_a_bot_exists() -> None:
    """`BOT-176`: it reads the stored bots, so neither a selection nor the lifecycle matters."""
    assert not export_plan_availability(0).enabled
    assert "no bot" in export_plan_availability(0).reason
    assert export_plan_availability(1).enabled
    assert export_plan_availability(7).enabled


def test_a_recovering_bots_resume_says_it_opens_the_session_and_books_fills() -> None:
    """`BUG-204`: the owner's way out of RECOVERING is Resume; its tooltip says what it does."""
    reason = availability(S.RECOVERING, A.RESUME).reason
    assert "order session" in reason
    assert "filled" in reason


def test_confirm_resume_stays_a_halted_bots_alone_when_a_recovering_bot_may_resume() -> (
    None
):
    """`BUG-204`: a RECOVERING bot has no proposal to confirm."""
    assert not availability(S.RECOVERING, A.CONFIRM_RESUME).enabled


def test_what_a_recovering_bot_cannot_do_says_it_is_waiting_for_resume() -> None:
    """`BUG-204`: Pause is disabled while Recovering; its tooltip says why and what to press."""
    reason = availability(S.RECOVERING, A.PAUSE).reason
    assert "recovering" in reason
    assert "waiting for Resume" in reason
