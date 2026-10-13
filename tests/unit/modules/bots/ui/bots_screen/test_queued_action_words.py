"""`BUG-202` — an accepted resume is not reported as done: it was only queued."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.queued_action_words import (
    accepted_words,
)

S = BotLifecycleState


def test_a_halted_bots_queued_resume_says_where_its_outcome_shows_never_done() -> None:
    words = accepted_words("Resume my grid", BotAction.RESUME, S.HALTED)

    assert "done" not in words
    assert "sent to the bot" in words
    assert "log" in words and "Plan" in words


def test_a_queued_confirmation_says_what_running_depends_on_never_done() -> None:
    words = accepted_words("Confirm resume my grid", BotAction.CONFIRM_RESUME, S.HALTED)

    assert "done" not in words
    assert "RUNNING once the ladder is laid" in words


def test_a_paused_bots_resume_proposes_nothing_and_keeps_done() -> None:
    assert (
        accepted_words("Resume my grid", BotAction.RESUME, S.PAUSED)
        == "Resume my grid: done."
    )


@pytest.mark.parametrize(
    "action", [BotAction.START, BotAction.PAUSE, BotAction.SAVE, BotAction.STOP, None]
)
def test_every_other_accepted_action_keeps_done(action: BotAction | None) -> None:
    assert accepted_words("Create my grid", action, S.HALTED) == "Create my grid: done."
