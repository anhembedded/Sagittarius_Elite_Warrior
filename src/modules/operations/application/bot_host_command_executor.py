"""A command file becomes the command the Bots tab dispatches (`EPIC-038J`).

One row per action: the contract command the bots module answers by dispatching the screen's
own `StopBotCommand`, `PauseBotCommand`, `ResumeBotCommand`, `StartBotCommand`, `EditBotCommand`, `CreateBotCommand` or `DeleteBotCommand` (and,
for the owner's `loss-cap-ack`, the acknowledgement of the account-level loss cap, `EPIC-026L`). So the file adds no
way to stop, pause, resume, start or edit a bot; it only
asks for one by name, and the lifecycle table, the read-only rule
and the real-money question apply as on the screen.

@par Extension cases
  · a new verb (`bot archive`) - one `HostControlAction` member and one row in `_REQUESTS` and
    in `_ACCEPTED_WORDS`; `start` (`EPIC-038K`) and `edit` (`EPIC-038L`) were added so.
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
from Sagittarius_Elite_Warrior.src.core.contracts.new_bot_entry import NewBotEntry
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    AcknowledgeLossCapForHostCommand,
    AddBotForHostCommand,
    DeleteBotForHostCommand,
    EditBotForHostCommand,
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

#: What an accepted command means, in the operator's words. A stop is asynchronous. An edit says
#: what it changed itself, so the host's own sentence (`BotCommandResult.message`) wins for it.
_ACCEPTED_WORDS: dict[HostControlAction, str] = {
    HostControlAction.STOP: (
        "the bot is STOPPING; it becomes STOPPED once the exchange shows no order of its "
        "left (see `bot show`)"
    ),
    HostControlAction.PAUSE: "the bot is PAUSED: it places no orders, its resting orders stay",
    HostControlAction.RESUME: "the bot is resuming (see `bot show`)",
    HostControlAction.START: "the bot is STARTING (see `bot show`)",
    HostControlAction.EDIT: "the bot's parameters were changed and it is DRAFT (see `bot show`)",
    HostControlAction.ADD: "the bot was created and is DRAFT (see `bot list`)",
    HostControlAction.DELETE: "the bot was deleted (see `bot list`)",
    HostControlAction.ACKNOWLEDGE_LOSS_CAP: (
        "the loss cap is acknowledged: bots may start again, and the day's loss keeps counting "
        "from 00:00 UTC (it trips again at the figure unless you raised it)"
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
    HostControlAction.EDIT: lambda c: EditBotForHostCommand(c.bot_id, c.settings),
    HostControlAction.ADD: lambda c: AddBotForHostCommand(_entry_of(c)),
    HostControlAction.DELETE: lambda c: DeleteBotForHostCommand(c.bot_id),
    HostControlAction.ACKNOWLEDGE_LOSS_CAP: lambda _c: (
        AcknowledgeLossCapForHostCommand()
    ),
}

#: The actions whose accepted answer names what the host did (a change, the new id), so the host's
#: own sentence is the reply.
_SAYS_ITS_OWN_WORDS = frozenset(
    {HostControlAction.EDIT, HostControlAction.ADD, HostControlAction.DELETE}
)


def _entry_of(command: HostCommand) -> NewBotEntry:
    """The codec refuses an add with no entry; this keeps the type honest, not a second check."""
    if command.entry is None:
        raise ValueError("an add carries an entry")
    return command.entry


def _accepted_words(command: HostCommand, result: BotCommandResult) -> str:
    """The host's own sentence for an edit, add or delete (it names what changed); the fixed words for every other action."""
    if command.action in _SAYS_ITS_OWN_WORDS and result.message:
        return result.message
    return _ACCEPTED_WORDS[command.action]


class BotHostCommandExecutor(IHostCommandExecutor):
    def __init__(self, dispatcher: ICommandDispatcher) -> None:
        self._dispatcher = dispatcher

    def execute(self, command: HostCommand) -> ExecutionOutcome:
        request = _REQUESTS[command.action](command)
        result = cast(
            BotCommandResult, self._dispatcher.dispatch(type(request), request)
        )
        if result.accepted:
            return ExecutionOutcome(True, _accepted_words(command, result))
        return ExecutionOutcome(False, result.message)
