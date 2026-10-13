"""`BUG-202` — an accepted resume is not reported as done: it was only queued."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.queued_action_words import (
    accepted_words,
)


@pytest.mark.parametrize("action", [BotAction.RESUME, BotAction.CONFIRM_RESUME])
def test_a_queued_resume_says_where_its_outcome_shows_never_done(
    action: BotAction,
) -> None:
    words = accepted_words(f"{action.value} my grid", action)

    assert "done" not in words
    assert "sent to the bot" in words
    assert "Plan" in words


@pytest.mark.parametrize(
    "action", [BotAction.START, BotAction.PAUSE, BotAction.SAVE, BotAction.STOP, None]
)
def test_every_other_accepted_action_keeps_done(action: BotAction | None) -> None:
    assert accepted_words("Create my grid", action) == "Create my grid: done."
