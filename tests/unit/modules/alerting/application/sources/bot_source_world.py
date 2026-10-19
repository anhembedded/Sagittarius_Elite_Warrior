"""The bots' status report over a dict, shared by the bot sources' tests."""

from __future__ import annotations

from dataclasses import replace

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusEntry,
    BotStatusReport,
    GetBotStatusReportQuery,
)

BOT = "g3n092"


class Bots(ICommandDispatcher):
    """The bots' status report over a dict: the one query the source asks."""

    def __init__(self, *entries: BotStatusEntry) -> None:
        self.entries = {entry.bot_id: entry for entry in entries}

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        if handler_class is not GetBotStatusReportQuery or not isinstance(
            input_dto, GetBotStatusReportQuery
        ):
            raise AssertionError(f"the source asked for {handler_class!r}")
        if input_dto.bot_id is None:
            return BotStatusReport(bots=tuple(self.entries.values()))
        entry = self.entries.get(input_dto.bot_id)
        return BotStatusReport(bots=() if entry is None else (entry,))

    def move(self, state: str, reason: str = "", detail: str = "") -> None:
        self.entries[BOT] = replace(
            self.entries[BOT], state=state, reason=reason, reason_detail=detail
        )


def entry(state: str = "RUNNING", reason: str = "") -> BotStatusEntry:
    return BotStatusEntry(
        bot_id=BOT,
        name="eth-grid",
        kind="grid",
        venue="spot_mainnet",
        symbol="ETHUSDT",
        state=state,
        reason=reason,
        run_started_at=None,
    )
