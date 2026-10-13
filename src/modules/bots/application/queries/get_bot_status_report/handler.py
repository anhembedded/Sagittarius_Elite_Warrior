"""`EPIC-038C` — handler for `GetBotStatusReportQuery`.

Built from the Bots tab's own queries, dispatched the way the tab dispatches
them (`ICommandDispatcher`), so a bot file is read by the store and by nothing
here. A file the store refused is listed with its path instead of being hidden:
the bot may own orders, and its file is the only record of them.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_probe import (
    IInstanceProbe,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot import (
    GetBotQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    BotList,
    ListBotsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusEntry,
    BotStatusReport,
    GetBotStatusReportQuery,
    UnreadableBotEntry,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    RefusedBotFile,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    restarts_into_recovering,
)

_FILE_SUFFIX = ".json"


@dataclass(frozen=True, slots=True)
class BotsStateDirectory:
    """Where the bots' files are, so a refused one can be named by its path."""

    path: Path


class GetBotStatusReportQueryHandler(
    IQueryHandler[GetBotStatusReportQuery, BotStatusReport]
):
    """The status of every bot, or of the one named."""

    def __init__(
        self,
        dispatcher: ICommandDispatcher,
        directory: BotsStateDirectory,
        probe: IInstanceProbe,
        instance: IInstanceAccess,
    ) -> None:
        self._dispatcher = dispatcher
        self._directory = directory
        self._probe = probe
        self._instance = instance

    def execute(self, query: GetBotStatusReportQuery) -> BotStatusReport:
        report = self._report(query)
        return replace(report, app_running=self._a_copy_is_running())

    def _a_copy_is_running(self) -> bool:
        """A writable copy holds the data root by definition - the process asking
        is that copy, so it need not probe its own lock (and wait out the probe's
        confirmations). A read-only copy (a second one, or a command that declined
        the lock) asks the lock."""
        return (not self._instance.read_only) or self._probe.is_held()

    def _report(self, query: GetBotStatusReportQuery) -> BotStatusReport:
        if query.bot_id is None:
            return self._report_of(self._list())
        snapshot = cast(
            "BotSnapshot | None",
            self._dispatcher.dispatch(GetBotQuery, GetBotQuery(query.bot_id)),
        )
        if snapshot is not None:
            return BotStatusReport(bots=(_entry_of(snapshot),))
        # No readable bot has this id: it is either unknown or a refused file.
        refused = tuple(
            file
            for file in self._list().refused
            if file.name == f"{query.bot_id}{_FILE_SUFFIX}"
        )
        return BotStatusReport(unreadable=self._unreadable(refused))

    def _list(self) -> BotList:
        return cast(BotList, self._dispatcher.dispatch(ListBotsQuery, ListBotsQuery()))

    def _report_of(self, listing: BotList) -> BotStatusReport:
        return BotStatusReport(
            bots=tuple(_entry_of(bot) for bot in listing.bots),
            unreadable=self._unreadable(listing.refused),
        )

    def _unreadable(
        self, refused: tuple[RefusedBotFile, ...]
    ) -> tuple[UnreadableBotEntry, ...]:
        return tuple(
            UnreadableBotEntry(
                bot_id=file.name.removesuffix(_FILE_SUFFIX),
                path=str(self._directory.path / file.name),
                reason=file.reason,
            )
            for file in refused
        )


def _entry_of(bot: BotSnapshot) -> BotStatusEntry:
    return BotStatusEntry(
        bot_id=bot.bot_id,
        name=bot.name,
        kind=bot.kind,
        venue=bot.venue.value,
        symbol=bot.symbol,
        state=bot.state.value,
        reason=bot.progress.reason if bot.progress is not None else "",
        run_started_at=bot.run_started_at,
        resting_orders=bot.progress.open_orders if bot.progress is not None else None,
        recovers_on_restart=restarts_into_recovering(bot.state),
    )
