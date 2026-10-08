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
)

S = BotLifecycleState
A = BotAction

#: The ADR's table, read once more by hand: what a user may do in each state.
LEGAL = {
    S.DRAFT: {A.START, A.SAVE, A.DELETE},
    S.STARTING: {A.STOP},
    S.RUNNING: {A.PAUSE, A.STOP},
    S.PAUSED: {A.RESUME, A.STOP},
    S.RECOVERING: {A.STOP},
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
