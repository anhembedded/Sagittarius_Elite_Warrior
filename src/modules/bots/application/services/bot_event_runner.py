"""`EPIC-029B` — load a bot, put one event through the lifecycle table, save it.

Pause, resume and stop differ only in the event they name, so the three
handlers share this rather than carry three copies of the same load, refuse and
save. Every refusal is a value (`BotCommandResult`); nothing is saved when the
table refuses.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    BotNotFoundError,
    IBotStore,
    StoredBot,
    UnreadableBotError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import (
    BotId,
    InvalidBotIdError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    InvalidBotTransitionError,
)

logger = logging.getLogger("App.Bots.Lifecycle")


class BotLookup:
    """A stored bot, or the refusal that explains why there is none."""

    def __init__(self, store: IBotStore) -> None:
        self._store = store

    def find(self, bot_id: str) -> StoredBot | BotCommandResult:
        try:
            return self._store.load(BotId(bot_id))
        except (InvalidBotIdError, BotNotFoundError):
            return BotCommandResult.refused(
                BotRefusal.NOT_FOUND, f"No bot {bot_id!r}", bot_id
            )
        except UnreadableBotError as exc:
            return BotCommandResult.refused(BotRefusal.UNREADABLE, str(exc), bot_id)


class BotEventRunner:
    """Applies one lifecycle event to one stored bot and saves the result."""

    def __init__(self, store: IBotStore, clock: IBotClock) -> None:
        self._store = store
        self._clock = clock
        self._lookup = BotLookup(store)

    def run(self, bot_id: str, event: BotLifecycleEvent) -> BotCommandResult:
        found = self._lookup.find(bot_id)
        if isinstance(found, BotCommandResult):
            return found
        try:
            changed = found.bot.apply(event, self._clock.now())
        except InvalidBotTransitionError as exc:
            return BotCommandResult.refused(
                BotRefusal.INVALID_TRANSITION, str(exc), bot_id
            )
        self._store.save(StoredBot(changed, found.runtime))
        logger.info(
            "Bot %s: %s -> %s on %s",
            bot_id,
            found.bot.state.value,
            changed.state.value,
            event.value,
        )
        return BotCommandResult.done(bot_id)
