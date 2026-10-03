"""`EPIC-029B` — handler for `DeleteBotCommand`.

Only DRAFT and STOPPED can be deleted: in every other state the bot may own
orders, a lease or a budget, and deleting its file would orphan them.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_event_runner import (
    BotLookup,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.delete_bot.command import (
    DeleteBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    InvalidBotTransitionError,
)

logger = logging.getLogger("App.Bots.Lifecycle")


class DeleteBotCommandHandler(ICommandHandler[DeleteBotCommand, BotCommandResult]):
    """Deletes a DRAFT or STOPPED bot's record."""

    def __init__(self, store: IBotStore) -> None:
        self._store = store
        self._lookup = BotLookup(store)

    def execute(self, command: DeleteBotCommand) -> BotCommandResult:
        found = self._lookup.find(command.bot_id)
        if isinstance(found, BotCommandResult):
            return found
        try:
            found.bot.require_deletable()
        except InvalidBotTransitionError as exc:
            return BotCommandResult.refused(
                BotRefusal.INVALID_TRANSITION, str(exc), command.bot_id
            )
        self._store.delete(found.bot.bot_id)
        logger.info("Deleted bot %s", command.bot_id)
        return BotCommandResult.done(command.bot_id)
