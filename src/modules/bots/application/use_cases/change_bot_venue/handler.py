"""`BOT-171` — handler for `ChangeBotVenueCommand`.

The rule lives in the aggregate (`Bot.moved_to`): a draft that never ran has no
order, lease or inventory on its venue, so moving it is a change of the
definition and nothing at the exchange. Saving publishes the change like any
other, so a screen showing the bot reads it again.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_lookup import (
    BotLookup,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.change_bot_venue.command import (
    ChangeBotVenueCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    IBotStore,
    StoredBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import BotVenueFixedError


class ChangeBotVenueCommandHandler(
    ICommandHandler[ChangeBotVenueCommand, BotCommandResult]
):
    """Moves a draft bot that never ran to another Spot venue."""

    def __init__(self, store: IBotStore) -> None:
        self._store = store
        self._lookup = BotLookup(store)

    def execute(self, command: ChangeBotVenueCommand) -> BotCommandResult:
        found = self._lookup.find(command.bot_id)
        if isinstance(found, BotCommandResult):
            return found
        if found.bot.definition.venue is command.venue:
            return BotCommandResult.done(command.bot_id)
        try:
            moved = found.bot.moved_to(command.venue)
        except BotVenueFixedError as exc:
            return BotCommandResult.refused(
                BotRefusal.VENUE_FIXED, str(exc), command.bot_id
            )
        self._store.save(StoredBot(moved, found.runtime))
        return BotCommandResult.done(command.bot_id)
