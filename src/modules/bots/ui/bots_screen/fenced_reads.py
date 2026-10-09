"""`EPIC-029F` — the Bots screen's reads, off the UI thread and fenced.

Four reads, each its own kind: the list, the planner's market numbers for
the selected bot, its fills, and what the exchange says about its symbol
and account (`BOT-174`). A newer read of a kind supersedes the older
one, whose answer is then dropped as stale (`async-ui-action-rule.md` §1):
selecting another bot while the first one's fills load never shows the first
one's fills. The presenter owns the trackers (one per kind) and hands them
here; this coordinator only runs, marshals and checks.

`drop_all()` is final: a read asked after it is refused here, never submitted,
because by then the app's pool may have shut down and would raise
(`BUG-149`).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from enum import Enum

from PySide6.QtCore import Signal
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import failure_detail
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_fills import (
    GetBotFillsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_exchange_facts import (
    GetExchangeFactsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    GetPlannerMarketQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    ListBotsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.ui_thread_relay import UiThreadRelay
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

logger = logging.getLogger("App.Bots.Screen")


class ReadKind(str, Enum):
    LIST = "list"
    PLANNER = "planner"
    FILLS = "fills"
    #: `EPIC-034D` — the selected bot's venue account; read by `ConnectStep`'s
    #: own `FencedReads`, so the screen's presenter never sees its answers.
    CONNECT = "connect"
    #: `BOT-174` — what the exchange says about the selected bot's symbol and
    #: account, the facts the exchange rules of its readiness are judged on.
    EXCHANGE = "exchange"


type ReadTrackers = Mapping[ReadKind, ActionOwnershipTracker[ReadKind, str, None]]


class FencedReads(UiThreadRelay):
    """@brief Runs one read per kind at a time; delivers only the newest."""

    #: The kind, the read's label, and its answer.
    answered = Signal(object, str, object)
    #: The kind, the read's label, and the technical text of what went wrong.
    failed = Signal(object, str, str)

    def __init__(self, thread_manager: IThreadManager, trackers: ReadTrackers) -> None:
        super().__init__()
        self._threads = thread_manager
        self._trackers = trackers
        self._dropped = False

    def read(self, kind: ReadKind, label: str, task: Callable[[], object]) -> None:
        if self._dropped:
            logger.debug(
                "Bots screen read %s (%s) refused: the screen has shut down",
                kind.value,
                label,
            )
            return
        action = self._trackers[kind].begin_action(kind, label, None)
        self._threads.submit(self._read_on_pool, kind, action.action_id, label, task)

    def abandon(self, kind: ReadKind) -> None:
        """The read of `kind` in flight, if any, is answered into nothing."""
        self._trackers[kind].invalidate_active()

    def drop_all(self) -> None:
        """Every read in flight is answered into nothing, and every later
        read is refused (shutdown)."""
        self._dropped = True
        for tracker in self._trackers.values():
            tracker.invalidate_active()

    def _read_on_pool(
        self, kind: ReadKind, action_id: int, label: str, task: Callable[[], object]
    ) -> None:
        try:
            self._report((kind, action_id, label, task(), None))
        except Exception as exc:  # noqa: BLE001 - worker boundary: the failure is shown in words, not lost to a pool thread
            self._report((kind, action_id, label, None, failure_detail(exc)))

    def _deliver(self, payload: object) -> None:
        if not isinstance(payload, tuple):
            raise TypeError(f"a read answers a tuple, not {type(payload).__name__}")
        kind, action_id, label, answer, detail = payload
        tracker = self._trackers[kind]
        if not tracker.is_current_pending(action_id, kind):
            tracker.log_stale_callback("_deliver", action_id, kind)
            return
        if detail is not None:
            tracker.finish_action(action_id, ActionOutcome.FAILED)
            # One line per failed operation (`logging-rule.md` §4): the engine's
            # dispatcher already wrote this failure at ERROR (`BUG-168` counted
            # it twice), so the screen's own record is DEBUG.
            logger.debug(
                "Bots screen read %s (%s) failed: %s", kind.value, label, detail
            )
            self.failed.emit(kind, label, detail)
            return
        tracker.finish_action(action_id, ActionOutcome.SUCCEEDED)
        self.answered.emit(kind, label, answer)


class BotQueries:
    """@brief The screen's three bots queries, each a fenced read."""

    def __init__(
        self,
        dispatcher: ICommandDispatcher,
        reads: FencedReads,
        selected: Callable[[], BotSnapshot | None],
    ) -> None:
        self._dispatcher = dispatcher
        self._reads = reads
        self._selected = selected

    def bots(self) -> None:
        self._read(ReadKind.LIST, "", ListBotsQuery())

    def planner(self, bot: BotSnapshot) -> None:
        self._read(
            ReadKind.PLANNER, bot.bot_id, GetPlannerMarketQuery(bot.venue, bot.symbol)
        )

    def fills(self, bot: BotSnapshot | None) -> None:
        if bot is not None:
            self._read(ReadKind.FILLS, bot.bot_id, GetBotFillsQuery(bot.bot_id))

    def exchange(self, bot: BotSnapshot) -> None:
        self._read(ReadKind.EXCHANGE, bot.bot_id, GetExchangeFactsQuery(bot.bot_id))

    def again(self, kind: ReadKind) -> None:
        """Asks `kind` once more, for the selected bot (Retry on its message bar)."""
        bot = self._selected()
        if kind is ReadKind.LIST:
            self.bots()
        elif kind is ReadKind.PLANNER and bot is not None:
            self.planner(bot)
        elif kind is ReadKind.EXCHANGE and bot is not None:
            self.exchange(bot)
        else:
            self.fills(bot)

    def _read(self, kind: ReadKind, label: str, query: object) -> None:
        dispatcher = self._dispatcher
        self._reads.read(kind, label, lambda: dispatcher.dispatch(type(query), query))
