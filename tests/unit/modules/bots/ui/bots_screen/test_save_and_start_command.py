"""`EPIC-034H`, decision D8 — Start is Save and start: the edits on screen
travel with the start when they differ from the saved parameters."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_commands import (
    command_for,
)

from .bots_screen_fixtures import GOOD_CONFIG, Answers, stored


def _bot() -> BotSnapshot:
    return BotSnapshot.of(stored("a00001", S.DRAFT).bot, None)


def test_start_without_edits_starts_the_saved_parameters() -> None:
    command = command_for(BotAction.START, _bot(), Answers().dialogs(), None)

    assert command == StartBotCommand("a00001", None, real_money_confirmed=True)


def test_start_with_edits_equal_to_the_saved_ones_saves_nothing() -> None:
    command = command_for(
        BotAction.START, _bot(), Answers().dialogs(), dict(GOOD_CONFIG)
    )

    assert command == StartBotCommand("a00001", None, real_money_confirmed=True)


def test_start_with_edits_carries_them_to_be_saved_first() -> None:
    edited = {**GOOD_CONFIG, "capital_quote": "1500"}

    command = command_for(BotAction.START, _bot(), Answers().dialogs(), edited)

    assert command == StartBotCommand("a00001", edited, real_money_confirmed=True)
