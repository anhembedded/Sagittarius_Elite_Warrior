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
        """A new executor for a new run, replacing any earlier one."""
        with self._lock:
            executor = self._factory.create(bot)
            self._executors[bot.bot_id.value] = executor
            return executor

    def get(self, bot_id: str) -> GridExecutor | None:
        with self._lock:
            return self._executors.get(bot_id)

    def all(self) -> tuple[GridExecutor, ...]:
        with self._lock:
            return tuple(self._executors.values())

    def on_venue(self, venue: TradingVenue) -> tuple[GridExecutor, ...]:
        with self._lock:
            return tuple(e for e in self._executors.values() if e.venue is venue)
