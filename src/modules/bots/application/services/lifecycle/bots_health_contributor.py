"""The bots' section of the health snapshot (`EPIC-038C`).

Counts of bots by state, read through `GetBotStatusReportQuery` - the same read
model `bot list` and `status` print - so the snapshot cannot disagree with them.
`running`, `paused` and `halted` are the three counts the host's health line
carries (`EPIC-038G`); `states` is the full tally. No bot name, symbol or
profit: counts and state names only.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_health_contributor import (
    IHealthContributor,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    UNREADABLE_STATE,
    BotStatusReport,
    GetBotStatusReportQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)

SECTION_NAME = "bots"


class BotsHealthContributor(IHealthContributor):
    @property
    def name(self) -> str:
        return SECTION_NAME

    def __init__(self, dispatcher: ICommandDispatcher) -> None:
        self._dispatcher = dispatcher

    def snapshot(self) -> Mapping[str, JsonValue]:
        report = cast(
            BotStatusReport,
            self._dispatcher.dispatch(
                GetBotStatusReportQuery, GetBotStatusReportQuery()
            ),
        )
        counts = report.state_counts()
        return {
            "total": len(report.bots),
            "running": counts.get(BotLifecycleState.RUNNING.value, 0),
            "paused": counts.get(BotLifecycleState.PAUSED.value, 0),
            "halted": counts.get(BotLifecycleState.HALTED.value, 0),
            "unreadable": counts.get(UNREADABLE_STATE, 0),
            "states": dict(counts),
        }
