"""`EPIC-029E` — the running bot's one record, and its one writer (ADR D4, D9).

Held by the bot's executor and touched only on the bot's worker. Every change
of the lifecycle goes through the table (`Bot.apply`), and every change of the
bot or its ladder is saved at once ("persist after acting": the tag makes a
write after a submit safe, because an order sent but never saved is still found
by its tag at reconciliation).

**A store that cannot write is a fact, not an exception** (`EPIC-035G`). The
memory changes first, so a save that raised left memory ahead of the file and
unwound whatever was acting, `GridTaskGuard`'s park included. `_save` now keeps
the failure (`storage_failure`) and returns, and the next write that succeeds
carries the whole true state, because every write is the whole record. It also
counts the failures in a row (`failed_saves`): `GridStorageWatch` pauses the bot
at three (owner decision D6), so it does not trade on memory indefinitely.

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
        self._storage_failure: str | None = None
        self._failed_saves = 0

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

    @property
    def storage_failure(self) -> str | None:
        """Why the last write failed, or `None` when it succeeded: memory is
        ahead of the file exactly while this is set."""
        return self._storage_failure

    @property
    def failed_saves(self) -> int:
        """How many writes in a row failed; a write that succeeds resets it."""
        return self._failed_saves

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

    def save_works(self) -> bool:
        """Write the record once more and say whether the store took it."""
        self._save()
        return self._storage_failure is None

    def _save(self) -> None:
        try:
            self._store.save(StoredBot(self._bot, encode_runtime(self._runtime)))
        except OSError as error:
            self._failed_saves += 1
            self._storage_failure = f"{type(error).__name__}: {error.strerror or error}"
            logger.error(
                "Bot %s: its state could not be saved, memory is ahead of the file "
                "until a write succeeds (%s) [bot-store-failed]",
                self.bot_id,
                self._storage_failure,
            )
            return
        self._failed_saves = 0
        if self._storage_failure is not None:
            logger.warning(
                "Bot %s: its state is saved again [bot-store-recovered]", self.bot_id
            )
            self._storage_failure = None
