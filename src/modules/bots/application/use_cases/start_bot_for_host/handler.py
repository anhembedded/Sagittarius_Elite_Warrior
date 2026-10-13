"""`EPIC-038D` - the host's "start this bot", answered by the screen's own Start.

The screen asks the question that names real money before it dispatches
`StartBotCommand(real_money_confirmed=True)`. A command line cannot ask, so the
operator answers in advance by typing the venue (decision O8). This handler is
where that answer is judged: the start carries the real-money confirmation only
when the typed venue is the bot's own, and otherwise nothing is dispatched.
"""

from __future__ import annotations

from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_lookup import (
    BotLookup,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    StartBotForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore


class StartBotForHostCommandHandler(
    ICommandHandler[StartBotForHostCommand, BotCommandResult]
):
    def __init__(self, store: IBotStore, dispatcher: ICommandDispatcher) -> None:
        self._lookup = BotLookup(store)
        self._dispatcher = dispatcher

    def execute(self, command: StartBotForHostCommand) -> BotCommandResult:
        found = self._lookup.find(command.bot_id)
        if isinstance(found, BotCommandResult):
            return found
        venue = found.bot.definition.venue
        if not venue.is_mainnet:
            return self._start(StartBotCommand(command.bot_id))
        if command.confirmed_venue != venue.value:
            return BotCommandResult.refused(
                BotRefusal.REAL_MONEY_NOT_CONFIRMED,
                f"Bot {command.bot_id} trades real money on {venue.display_name}. "
                f"Starting it from the command line needs --confirm-venue {venue.value}.",
                command.bot_id,
            )
        return self._start(StartBotCommand(command.bot_id, real_money_confirmed=True))

    def _start(self, command: StartBotCommand) -> BotCommandResult:
        return cast(
            BotCommandResult, self._dispatcher.dispatch(StartBotCommand, command)
        )
