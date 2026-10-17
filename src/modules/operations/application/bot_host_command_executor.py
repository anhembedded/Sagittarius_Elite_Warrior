"""A command file becomes the command the Bots tab dispatches (`EPIC-038J`).

One row per action: the contract command the bots module answers by dispatching the screen's
own `StopBotCommand`, `PauseBotCommand`, `ResumeBotCommand`, `StartBotCommand` or
`DeleteBotCommand`. So the file adds no way to stop, pause, resume, start or delete a bot; it only
asks for one by name, and the lifecycle table, the read-only rule
and the real-money question apply as on the screen.

@par Extension cases
  · a new verb (`bot archive`) - one `HostControlAction` member and one row in `_REQUESTS` and
    in `_ACCEPTED_WORDS`; `start` and `delete` (`EPIC-038K`) were added so.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    DeleteBotForHostCommand,
    PauseBotForHostCommand,
    ResumeBotForHostCommand,
    StartBotForHostCommand,
    StopBotForOperatorCommand,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_command import (
    HostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_command_executor import (
    ExecutionOutcome,
    IHostCommandExecutor,
)

#: What an accepted command means, in the operator's words. A stop is asynchronous.
_ACCEPTED_WORDS: dict[HostControlAction, str] = {
    HostControlAction.STOP: (
        "the bot is STOPPING; it becomes STOPPED once the exchange shows no order of its "
        "left (see `bot show`)"
    ),
    HostControlAction.PAUSE: "the bot is PAUSED: it places no orders, its resting orders stay",
    HostControlAction.RESUME: "the bot is resuming (see `bot show`)",
    HostControlAction.START: "the bot is STARTING (see `bot show`)",
    HostControlAction.DELETE: (
        "the bot is deleted and cannot be restored; if the applied plan still names it, "
        "`run --start-planned` warns about it until the plan is applied again with `bot apply`"
    ),
}

type _Request = Callable[[HostCommand], object]

_REQUESTS: dict[HostControlAction, _Request] = {
    HostControlAction.STOP: lambda c: StopBotForOperatorCommand(
        c.bot_id, c.confirmed_venue, c.close_position
    ),
    HostControlAction.PAUSE: lambda c: PauseBotForHostCommand(c.bot_id),
    HostControlAction.RESUME: lambda c: ResumeBotForHostCommand(
        c.bot_id, c.confirmed_venue
    ),
    HostControlAction.START: lambda c: StartBotForHostCommand(
        c.bot_id, c.confirmed_venue
    ),
    HostControlAction.DELETE: lambda c: DeleteBotForHostCommand(c.bot_id),
}


class BotHostCommandExecutor(IHostCommandExecutor):
    def __init__(self, dispatcher: ICommandDispatcher) -> None:
        self._dispatcher = dispatcher

    def execute(self, command: HostCommand) -> ExecutionOutcome:
        request = _REQUESTS[command.action](command)
        result = cast(
            BotCommandResult, self._dispatcher.dispatch(type(request), request)
        )
        if result.accepted:
            return ExecutionOutcome(True, _ACCEPTED_WORDS[command.action])
        return ExecutionOutcome(False, result.message)
