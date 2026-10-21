"""`EPIC-045G` - the host's "move this bot to another venue", answered by the screen's own Venue field.

The Bots tab's Venue field moves a DRAFT that never ran between Spot venues (the usual use: designed
on the testnet, then moved to mainnet). Until now the host's nearest thing was `bot delete` then
`bot add`, which makes a new bot id; the owner's rule (2026-10-21) is that the host does what the tab
does. This handler is that move reached through the command directory. It adds no way to move a bot: it
dispatches the very `ChangeBotVenueCommand` the tab dispatches, so the aggregate's rule (`Bot.moved_to`:
a Spot bot, a DRAFT, never run) is the tab's, and the bot keeps its id.

Order, so that a refusal changes nothing and says why:
  1. the venue is one this build trades on;
  2. no other bot already has this bot's name on that venue (the identity a plan uses);
  3. the move is dispatched, and the reply names the venue and how to start the bot.

A move places no order and needs no `--confirm-venue`, on a mainnet venue too: the real-money question
stays at `bot start`, whose guard is untouched. A moved bot is not in `state/bot_plan.json`'s desired
states and its plan entry, if any, is the operator's to change.

@par Concurrency
Everything runs under `BotCommandLock`, the lock a Start, an Edit, an Add and a Delete hold, so a Start
cannot read the bots half way through a move and two moves cannot both pass step 2.
"""

from __future__ import annotations

from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_command_lock import (
    BotCommandLock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_identity import (
    bot_with_name_on,
    venue_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_lookup import (
    BotLookup,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.change_bot_venue import (
    ChangeBotVenueCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    MoveBotForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    IBotStore,
    StoredBot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class MoveBotForHostCommandHandler(
    ICommandHandler[MoveBotForHostCommand, BotCommandResult]
):
    def __init__(
        self, store: IBotStore, dispatcher: ICommandDispatcher, lock: BotCommandLock
    ) -> None:
        self._store = store
        self._lookup = BotLookup(store)
        self._dispatcher = dispatcher
        self._lock = lock

    def execute(self, command: MoveBotForHostCommand) -> BotCommandResult:
        with self._lock.held():
            found = self._lookup.find(command.bot_id)
            if isinstance(found, BotCommandResult):
                return found
            venue = venue_of(command.venue)
            if not isinstance(venue, TradingVenue):
                return _refused(venue, command.bot_id)
            was = found.bot.definition.venue
            if venue is was:
                return _refused(
                    f"Bot {command.bot_id} is already on {venue.value}", command.bot_id
                )
            problem = self._duplicate_problem(found, venue)
            if problem:
                return _refused(problem, command.bot_id)
            result = cast(
                BotCommandResult,
                self._dispatcher.dispatch(
                    ChangeBotVenueCommand,
                    ChangeBotVenueCommand(command.bot_id, venue),
                ),
            )
            if not result.accepted:
                return BotCommandResult.refused(
                    result.refusal or BotRefusal.VENUE_FIXED,
                    f"{result.message} Nothing was moved.",
                    command.bot_id,
                )
            return BotCommandResult(
                accepted=True,
                bot_id=command.bot_id,
                message=_accepted_words(command.bot_id, was, venue),
            )

    def _duplicate_problem(self, found: StoredBot, venue: TradingVenue) -> str:
        name = found.bot.definition.name
        other = bot_with_name_on(self._store, name, venue)
        if other is None:
            return ""
        return (
            f"bot {other.bot.bot_id.value} already has the name {name!r} on {venue.value}; "
            "delete one of the two (`bot delete`) or leave this bot on its venue"
        )


def _refused(words: str, bot_id: str) -> BotCommandResult:
    return BotCommandResult.refused(
        BotRefusal.INVALID_DEFINITION, f"{words}. Nothing was moved.", bot_id
    )


def _accepted_words(bot_id: str, was: TradingVenue, venue: TradingVenue) -> str:
    flag = f" --confirm-venue {venue.value}" if venue.is_mainnet else ""
    return (
        f"bot {bot_id} moved from {was.value} to {venue.value}; it is still DRAFT and starts only when "
        f"you `bot start {bot_id}{flag}`. Its plan-file entry, if any, still names {was.value}: "
        "change it too, or the next `bot apply` creates a second bot"
    )
