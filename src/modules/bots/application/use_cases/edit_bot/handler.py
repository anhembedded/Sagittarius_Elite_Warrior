"""`EPIC-029B` — handler for `EditBotCommand`.

Kind, venue and symbol are not editable: the bot's orders, lease and derived
inventory are tied to them (ADR D6), so changing one is a new bot.
"""

from __future__ import annotations

from dataclasses import replace

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_event_runner import (
    BotLookup,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.edit_bot.command import (
    EditBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    IBotStore,
    StoredBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    InvalidBotTransitionError,
)


class EditBotCommandHandler(ICommandHandler[EditBotCommand, BotCommandResult]):
    """Replaces a DRAFT or STOPPED bot's name and parameters; it lands on DRAFT."""

    def __init__(self, store: IBotStore, clock: IBotClock) -> None:
        self._store = store
        self._clock = clock
        self._lookup = BotLookup(store)

    def execute(self, command: EditBotCommand) -> BotCommandResult:
        found = self._lookup.find(command.bot_id)
        if isinstance(found, BotCommandResult):
            return found
        try:
            definition = replace(
                found.bot.definition, name=command.name.strip(), config=command.config
            )
        except ValueError as exc:
            return BotCommandResult.refused(
                BotRefusal.INVALID_DEFINITION, str(exc), command.bot_id
            )
        try:
            edited = found.bot.edited(definition, self._clock.now())
        except InvalidBotTransitionError as exc:
            return BotCommandResult.refused(
                BotRefusal.INVALID_TRANSITION, str(exc), command.bot_id
            )
        self._store.save(StoredBot(edited, found.runtime))
        return BotCommandResult.done(command.bot_id)
