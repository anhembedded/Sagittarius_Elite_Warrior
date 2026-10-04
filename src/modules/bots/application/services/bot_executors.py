"""`EPIC-029E` — the executors of the bots that have one (ADR D9).

One executor per bot, built when the bot first needs one: at start, or when a
restored bot is resumed, stopped or reconciled. The handlers find a bot's
executor here by its id, which is also its tag (D5), or every executor on a
venue for a switch event.
"""

from __future__ import annotations

import threading

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_executor import (
    GridExecutor,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_executor_factory import (
    GridExecutorFactory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class BotExecutors:
    """Executors by bot id; built on first need, replaced on a new run."""

    def __init__(self, factory: GridExecutorFactory) -> None:
        self._factory = factory
        self._lock = threading.Lock()
        self._executors: dict[str, GridExecutor] = {}

    def for_bot(self, bot: Bot) -> GridExecutor:
        """The bot's executor, built from the store when it has none yet."""
        with self._lock:
            executor = self._executors.get(bot.bot_id.value)
            if executor is None:
                executor = self._factory.create(bot)
                self._executors[bot.bot_id.value] = executor
            return executor

    def fresh(self, bot: Bot) -> GridExecutor:
        """A new executor for a new run, closing any earlier one's worker."""
        with self._lock:
            replaced = self._executors.get(bot.bot_id.value)
            executor = self._factory.create(bot)
            self._executors[bot.bot_id.value] = executor
        if replaced is not None:
            replaced.close()
        return executor

    def retire(self, bot_id: str) -> None:
        """Close the bot's worker, after it runs what is queued, and forget it.
        A new run calls this before writing its bot, so no task of the old
        run saves a stale bot over the new one's file.

        The join runs on the caller's thread, under the start lock when the
        runner calls it. A DRAFT or STOPPED bot's worker is idle, so it
        returns at once; a task still in a network call (a stop that is
        retrying) would hold every start until that call returns, which is
        the request timeout of the venue's client (PR 325 review, accepted:
        a bounded join would let the stale task write after the new run)."""
        with self._lock:
            executor = self._executors.pop(bot_id, None)
        if executor is not None:
            executor.close()

    def close_all(self) -> None:
        """Close every worker (module shutdown)."""
        with self._lock:
            executors = tuple(self._executors.values())
            self._executors.clear()
        for executor in executors:
            executor.close()

    def get(self, bot_id: str) -> GridExecutor | None:
        with self._lock:
            return self._executors.get(bot_id)

    def all(self) -> tuple[GridExecutor, ...]:
        with self._lock:
            return tuple(self._executors.values())

    def on_venue(self, venue: TradingVenue) -> tuple[GridExecutor, ...]:
        with self._lock:
            return tuple(e for e in self._executors.values() if e.venue is venue)
