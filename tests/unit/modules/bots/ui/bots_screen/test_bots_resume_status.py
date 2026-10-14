"""`BUG-202` — the Bots screen does not report a queued resume as done."""

from __future__ import annotations

from typing import Any

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_ui_fsm_matrix import (
    BotsUiState,
)

from .bots_screen_fixtures import BotsScreen, stored

S = BotLifecycleState


def _status_after_resume(screen: BotsScreen, qtbot: Any) -> str:
    screen.view.model.select_requested.emit("a00001")
    screen.settle()
    screen.view.model.action_requested.emit(BotAction.RESUME.value)
    screen.settle()
    assert screen.presenter.fsm is not None
    qtbot.waitUntil(
        lambda: screen.presenter.fsm.current_state is not BotsUiState.ACTION_IN_FLIGHT
    )
    return screen.view.status.text()


def test_an_accepted_resume_of_a_halted_bot_is_not_reported_done(
    open_bots_screen, qtbot
) -> None:
    """The command was only queued; the bot may stay HALTED."""
    screen = open_bots_screen([stored("a00001", S.HALTED)])
    screen.settle()

    status = _status_after_resume(screen, qtbot)

    assert status.startswith("Resume ") and "sent to the bot" in status
    assert "done" not in status


def test_an_accepted_resume_of_a_paused_bot_still_says_done(
    open_bots_screen, qtbot
) -> None:
    screen = open_bots_screen([stored("a00001", S.PAUSED)])
    screen.settle()

    status = _status_after_resume(screen, qtbot)

    assert status.endswith(": done.")
