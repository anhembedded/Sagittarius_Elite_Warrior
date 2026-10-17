"""`EPIC-038D` - the host's "stop this bot", answered by the screen's own Stop."""

from __future__ import annotations

from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    StopBotForHostCommand,
)


class StopBotForHostCommandHandler(
    ICommandHandler[StopBotForHostCommand, BotCommandResult]
):
    """Dispatches `StopBotCommand` with the command's exposure handling: cancel the bot's
    tagged orders, confirm none are open, STOPPED. It keeps the base unless asked to close
    it. The lifecycle table decides whether the bot may stop; a refusal comes back as it
    would on the screen."""

    def __init__(self, dispatcher: ICommandDispatcher) -> None:
        self._dispatcher = dispatcher

    def execute(self, command: StopBotForHostCommand) -> BotCommandResult:
        return cast(
            BotCommandResult,
            self._dispatcher.dispatch(
                StopBotCommand, StopBotCommand(command.bot_id, command.exposure)
            ),
        )
