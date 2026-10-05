"""`EPIC-029F` — the preview builds the screen offline, every state listed."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    BotsView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.preview import (
    build_preview,
)


def test_the_preview_lists_a_bot_in_every_state_and_selects_a_draft(qtbot) -> None:
    view = build_preview()
    qtbot.addWidget(view)

    assert isinstance(view, BotsView)
    assert {bot.state for bot in view.model.bots} == set(BotLifecycleState)
    assert view.model.selected is not None
    assert view.model.selected.state is BotLifecycleState.DRAFT
    assert view.model.availability
