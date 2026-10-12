"""`EPIC-038C` - the pieces `status` reads, as in-memory implementations of their ports.

Each double subclasses the port it stands for (`testing-rule.md` §2): the lock
probe, the snapshot source and the clock are three small ABCs, and the bots come
from the real read handlers over the in-memory store.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_health_contributor import (
    IHealthContributor,
    IHealthContributors,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_probe import (
    IInstanceProbe,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.queries.get_host_status import (
    GetHostStatusQuery,
    GetHostStatusQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.health_snapshot import (
    HealthSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_health_snapshot_sink import (
    IHealthSnapshotSink,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_health_snapshot_source import (
    HealthSnapshotUnreadableError,
    IHealthSnapshotSource,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.helpers import seed
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.status_world import (
    BotQueryDispatcher,
)

NOW = datetime(2026, 10, 12, 12, 0, 0, tzinfo=UTC)
INTERVAL_S = 10


class FixedClock(IOperationsClock):
    def __init__(self, now: datetime = NOW) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current


class StubProbe(IInstanceProbe):
    def __init__(self, held: bool) -> None:
        self.held = held

    def is_held(self) -> bool:
        return self.held


class StubSource(IHealthSnapshotSource):
    def __init__(
        self, snapshot: HealthSnapshot | None, unreadable: str | None = None
    ) -> None:
        self.snapshot = snapshot
        self.unreadable = unreadable

    def read(self) -> HealthSnapshot | None:
        if self.unreadable is not None:
            raise HealthSnapshotUnreadableError(self.unreadable)
        return self.snapshot


class FixedContributor(IHealthContributor):
    def __init__(self, name: str, section: Mapping[str, JsonValue]) -> None:
        self._name = name
        self._section = section

    @property
    def name(self) -> str:
        return self._name

    def snapshot(self) -> Mapping[str, JsonValue]:
        return self._section


class RecordingSink(IHealthSnapshotSink):
    def __init__(self) -> None:
        self.published: list[HealthSnapshot] = []

    def publish(self, snapshot: HealthSnapshot) -> None:
        self.published.append(snapshot)


class FixedContributors(IHealthContributors):
    def __init__(self, *contributors: IHealthContributor) -> None:
        self._contributors = contributors

    def contributors(self) -> tuple[IHealthContributor, ...]:
        return self._contributors


def snapshot_aged(
    seconds: int,
    sections: Mapping[str, Mapping[str, JsonValue]] | None = None,
    host_state: HostState = HostState.SERVING,
) -> HealthSnapshot:
    return HealthSnapshot(
        app_version="1.2.3",
        pid=4242,
        started_at=NOW - timedelta(hours=1),
        written_at=NOW - timedelta(seconds=seconds),
        interval_s=INTERVAL_S,
        host_state=host_state,
        sections=sections or {"bots": {"total": 2}},
    )


def seeded_bots() -> FakeBotStore:
    store = FakeBotStore()
    seed(store, "aaaaaa", BotLifecycleState.RUNNING)
    seed(store, "bbbbbb", BotLifecycleState.HALTED)
    return store


class HostStatusDispatcher(ICommandDispatcher):
    """The bots' reads plus `GetHostStatusQuery`, over the doubles above."""

    def __init__(
        self, probe: IInstanceProbe, source: IHealthSnapshotSource, bots: FakeBotStore
    ) -> None:
        self._bots = BotQueryDispatcher(bots, probe)
        self._status = GetHostStatusQueryHandler(
            probe, source, self._bots, FixedClock()
        )

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        if handler_class is GetHostStatusQuery:
            return self._status.execute(GetHostStatusQuery())
        return self._bots.dispatch(handler_class, input_dto)
