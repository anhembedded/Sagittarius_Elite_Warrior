"""`EPIC-029B` — handler for `CreateBotCommand`."""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot.command import (
    CreateBotCommand,
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
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot, BotDefinition
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import (
    BotId,
    BotIdGenerator,
)

logger = logging.getLogger("App.Bots.Lifecycle")

#: 36⁶ ≈ 2.2 billion ids: one collision in a store of a few dozen bots is
#: already unlikely, eight in a row means the generator is broken, not unlucky.
MAX_ID_ATTEMPTS = 8


class IdSpaceExhaustedError(RuntimeError):
    """`MAX_ID_ATTEMPTS` draws in a row were all taken: the generator is broken."""


class CreateBotCommandHandler(ICommandHandler[CreateBotCommand, BotCommandResult]):
    """Saves a new DRAFT bot under an id no other file holds."""

    def __init__(self, store: IBotStore, clock: IBotClock, ids: BotIdGenerator) -> None:
        self._store = store
        self._clock = clock
        self._ids = ids

    def execute(self, command: CreateBotCommand) -> BotCommandResult:
        try:
            definition = BotDefinition(
                name=command.name.strip(),
                kind=command.kind,
                venue=command.venue,
                symbol=command.symbol.strip().upper(),
                config=command.config,
            )
        except ValueError as exc:
            return BotCommandResult.refused(BotRefusal.INVALID_DEFINITION, str(exc))
        bot = Bot.draft(self._free_id(), definition, self._clock.now())
        self._store.save(StoredBot(bot))
        logger.info(
            "Created bot %s (%s on %s)", bot.bot_id, definition.kind, definition.symbol
        )
        return BotCommandResult.done(bot.bot_id.value)

    def _free_id(self) -> BotId:
        for _ in range(MAX_ID_ATTEMPTS):
            candidate = self._ids.next_id()
            if not self._store.exists(candidate):
                return candidate
        raise IdSpaceExhaustedError(
            f"{MAX_ID_ATTEMPTS} bot ids in a row were already taken"
        )
