"""`EPIC-038K` - the host's "delete this bot", answered by the screen's own Delete.

It adds no way to delete: it dispatches `DeleteBotCommand`, whose handler accepts a DRAFT or
STOPPED bot only (`permits_delete`; in every other state the bot may own orders, a lease or a
budget). Delete places no order, so there is no real-money question and no venue is typed.

The applied plan (`state/bot_plan.json`) is left alone: `bot apply` is its one writer, and a
second writer inside the running host would make the record say something the operator never
applied. A plan that still names the deleted bot is already a WARNING for `--start-planned`
(a planned id that no bot has), and the operator's next `bot apply` makes the record and the
stored bots agree again; the verb's answer says so.
"""

from __future__ import annotations

from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.delete_bot import (
    DeleteBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    DeleteBotForHostCommand,
)


class DeleteBotForHostCommandHandler(
    ICommandHandler[DeleteBotForHostCommand, BotCommandResult]
):
    """Dispatches `DeleteBotCommand`. The lifecycle table decides whether the bot may be deleted;
    a refusal comes back as it would on the screen."""

    def __init__(self, dispatcher: ICommandDispatcher) -> None:
        self._dispatcher = dispatcher

    def execute(self, command: DeleteBotForHostCommand) -> BotCommandResult:
        return cast(
            BotCommandResult,
            self._dispatcher.dispatch(
                DeleteBotCommand, DeleteBotCommand(command.bot_id)
            ),
        )
