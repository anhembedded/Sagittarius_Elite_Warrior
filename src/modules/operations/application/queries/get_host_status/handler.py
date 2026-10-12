"""`EPIC-038C` - handler for `GetHostStatusQuery`.

Reads, in order: the lock (`IInstanceProbe`), the snapshot (`IHealthSnapshotSource`)
and the bots (`GetBotStatusReportQuery`, the Bots tab's own queries). It writes
nothing and takes no lock, so it works beside a running host and with none.
"""

from __future__ import annotations

from dataclasses import replace
from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_probe import (
    IInstanceProbe,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusReport,
    GetBotStatusReportQuery,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.queries.get_host_status.liveness import (
    decide_liveness,
    snapshot_age_s,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.queries.get_host_status.query import (
    GetHostStatusQuery,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.queries.get_host_status.result import (
    HostStatus,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.health_snapshot import (
    HealthSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_health_snapshot_source import (
    HealthSnapshotUnreadableError,
    IHealthSnapshotSource,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)


class GetHostStatusQueryHandler(IQueryHandler[GetHostStatusQuery, HostStatus]):
    """Decides what an observer may say about the host."""

    def __init__(
        self,
        probe: IInstanceProbe,
        source: IHealthSnapshotSource,
        dispatcher: ICommandDispatcher,
        clock: IOperationsClock,
    ) -> None:
        self._probe = probe
        self._source = source
        self._dispatcher = dispatcher
        self._clock = clock

    def execute(self, query: GetHostStatusQuery) -> HostStatus:
        now = self._clock.now()
        lock_held = self._probe.is_held()
        snapshot, problem = self._snapshot()
        liveness, reason = decide_liveness(lock_held, snapshot, problem, now)
        return HostStatus(
            liveness=liveness,
            reason=reason,
            lock_held=lock_held,
            snapshot=snapshot,
            snapshot_age_s=snapshot_age_s(snapshot, now),
            bots=self._bots(lock_held),
            checked_at=now,
        )

    def _bots(self, lock_held: bool) -> BotStatusReport:
        """The bots, with `app_running` taken from the one lock probe this query
        made, so `host.lock_held` and `app_running` cannot disagree in a report."""
        report = cast(
            BotStatusReport,
            self._dispatcher.dispatch(
                GetBotStatusReportQuery, GetBotStatusReportQuery()
            ),
        )
        return replace(report, app_running=lock_held)

    def _snapshot(self) -> tuple[HealthSnapshot | None, str]:
        try:
            return self._source.read(), ""
        except HealthSnapshotUnreadableError as unreadable:
            return None, f"the health snapshot cannot be used: {unreadable}"
