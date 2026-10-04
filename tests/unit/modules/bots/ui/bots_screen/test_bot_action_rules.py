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
    S.STOPPING: set(),
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


def test_unsaved_edits_block_start_before_the_verdict_is_named() -> None:
    both = StartConditions(refusal="Refused: too small", unsaved_edits=True)

    assert availability(S.DRAFT, A.START, both).reason == (
        "Save the changed parameters first."
    )
    refused = availability(S.DRAFT, A.START, StartConditions(refusal="Refused: x"))
    assert (refused.enabled, refused.reason) == (False, "Refused: x")


def test_a_refusal_never_blocks_an_action_other_than_start() -> None:
    refused = StartConditions(refusal="Refused: x", unsaved_edits=True)

    assert availability(S.DRAFT, A.SAVE, refused).enabled
    assert availability(S.RUNNING, A.STOP, refused).enabled
