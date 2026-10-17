"""`EPIC-038J` - the host's "pause this bot", answered by the screen's own Pause."""

from __future__ import annotations

from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.pause_bot import (
    PauseBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    PauseBotForHostCommand,
)


class PauseBotForHostCommandHandler(
    ICommandHandler[PauseBotForHostCommand, BotCommandResult]
):
    """Dispatches `PauseBotCommand`. The lifecycle table decides whether the bot may pause;
    a refusal comes back as it would on the screen."""

    def __init__(self, dispatcher: ICommandDispatcher) -> None:
        self._dispatcher = dispatcher

    def execute(self, command: PauseBotForHostCommand) -> BotCommandResult:
        return cast(
            BotCommandResult,
            self._dispatcher.dispatch(PauseBotCommand, PauseBotCommand(command.bot_id)),
        )
