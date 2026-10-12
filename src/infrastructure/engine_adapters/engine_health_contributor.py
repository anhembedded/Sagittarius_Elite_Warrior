"""The Engine's own health check, as one section of the health snapshot (`EPIC-038C`).

The Engine measures three things about the running process - the container, the
event bus and the database - in `HealthCheckQuery`. The snapshot reports that
result instead of measuring it again (`CONSTITUTION.md` P5: a sound mechanism
that exists comes first). It is a section like any other (`engine`), so
`status --json` shows it beside `bots` and `trading`.

Why `IHealthContributor` exists beside the Engine's extension, not instead of
it: the Engine's check is a fixed set of components that cannot be extended by
registration, and it is read only inside its own process - a second process
(`status`) cannot call it. The contributors add what the Engine does not know
(the bots, the user stream, the feeds) and the snapshot file carries all of them
to the reader.

Only the verdict and each component's one-word state are published; the Engine's
strings name a component, never a connection string or a path.
"""

from __future__ import annotations

from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.core.contracts.i_health_contributor import (
    DEGRADED,
    REASON_KEY,
    STATUS_KEY,
    IHealthContributor,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue
from sagittarius_engine.extensions.health.health_check_query import HealthCheckQuery
from sagittarius_engine.interfaces import IContainer, IEventBus

SECTION_NAME = "engine"
#: The word `HealthCheckQuery` uses for "all components ok".
HEALTHY = "healthy"


class EngineHealthContributor(IHealthContributor):
    """Reports `HealthCheckQuery`'s result."""

    def __init__(self, container: IContainer, event_bus: IEventBus) -> None:
        self._query = HealthCheckQuery(container, event_bus)

    @property
    def name(self) -> str:
        return SECTION_NAME

    def snapshot(self) -> Mapping[str, JsonValue]:
        result = self._query.execute()
        verdict = str(result.get("status", "unknown"))
        components: dict[str, JsonValue] = {
            str(key): str(value) for key, value in result.get("components", {}).items()
        }
        section: dict[str, JsonValue] = {"verdict": verdict, "components": components}
        if verdict != HEALTHY:
            # The general rule (`IHealthContributor`): a section that says it is
            # not well makes `status` exit 11.
            section[STATUS_KEY] = DEGRADED
            section[REASON_KEY] = "the Engine's health check reports " + verdict
        return section
