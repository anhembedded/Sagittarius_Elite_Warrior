"""`EPIC-029E` — the running bot's one record, and its one writer (ADR D4, D9).

Held by the bot's executor and touched only on the bot's worker. Every change
of the lifecycle goes through the table (`Bot.apply`), and every change of the
bot or its ladder is saved at once ("persist after acting": the tag makes a
write after a submit safe, because an order sent but never saved is still found
by its tag at reconciliation).

Each transition logs one line, `Bot <id>: <from> -> <to> on <event>`, with the
reason the runtime records when there is one (`logging-rule.md`).
"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_runtime_codec import (
    encode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    IBotStore,
    StoredBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    BotLifecycleState,
    is_declared,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    GridRuntime,
)

logger = logging.getLogger("App.Bots.GridExecutor")


class BotRunState:
    """The bot and its ladder, saved after every change."""

    def __init__(
        self, bot: Bot, runtime: GridRuntime, store: IBotStore, clock: IBotClock
    ) -> None:
        self._bot = bot
        self._runtime = runtime
        self._store = store
        self._clock = clock

    @property
    def bot(self) -> Bot:
        return self._bot

    @property
    def runtime(self) -> GridRuntime:
        return self._runtime

    @property
    def state(self) -> BotLifecycleState:
        return self._bot.state

    @property
    def bot_id(self) -> str:
        return self._bot.bot_id.value

    def now(self) -> datetime:
        return self._clock.now()

    def can(self, event: BotLifecycleEvent) -> bool:
        return is_declared(self._bot.state, event)

    def update(self, runtime: GridRuntime) -> None:
        """Keep and save the ladder after a change."""
        self._runtime = runtime
        self._save()

    def transition(
        self,
        event: BotLifecycleEvent,
        reason: GridReason | None = None,
        detail: str = "",
    ) -> None:
        """Apply `event`, record `reason` when given, and save.

        @raise InvalidBotTransitionError The table does not declare it."""
        before = self._bot.state
        self._bot = self._bot.apply(event, self._clock.now())
        if reason is not None:
            self._runtime = self._runtime.with_reason(reason, detail)
        elif event is BotLifecycleEvent.START:
            self._runtime = replace(self._runtime, reason=None, reason_detail="")
        self._save()
        logger.info(
            "Bot %s: %s -> %s on %s%s",
            self.bot_id,
            before.value,
            self._bot.state.value,
            event.value,
            f" ({reason.value}: {detail})" if reason is not None else "",
        )

    def _save(self) -> None:
        self._store.save(StoredBot(self._bot, encode_runtime(self._runtime)))
