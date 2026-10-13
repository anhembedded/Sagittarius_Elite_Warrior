"""`alerting` - alerts reach the owner when the owner is away (`EPIC-036`, N1).

**The context's one question:** *when something the owner must know happens, how
does it reach them, once, even if a channel is down or the app restarts?* It
listens (`EPIC-036B` brings the sources that read `bots` and `trading` events);
no context depends on it, so a new kind of bot changes nothing here.

What it holds today (`EPIC-036A`):

  - the typed `Alert`, `IAlertChannel` and the `AlertHub` that dedups, groups,
    inhibits, holds for quiet hours and routes;
  - a SQLite **outbox** under `<data root>/state/`, so an alert survives a restart
    and a dead network, and expires after 24 h instead of being sent late;
  - a **worker**, one lane per channel: priority, `retry_after`, bounded attempts,
    fail-over for CRITICAL, `CHANNEL_FAILING` when a channel gives up;
  - a health section: how many alerts wait and how long the oldest has.

It ships no real channel: `composition/channel_bindings.py` is where one is added.
A read-only copy of the data root opens no outbox and starts no lane.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.bounded_context_module import (
    BoundedContextModule,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_operations_registry import (
    HealthContributorDescriptor,
    IOperationsRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.threaded_delivery_host import (
    ThreadedDeliveryHost,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.alert_hub import (
    AlertHub,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.alerting_health_contributor import (
    SECTION_NAME,
    AlertingHealthContributor,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.composition.alerting_bindings import (
    bind_alerting,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_outbox import IOutbox
from sagittarius_engine.interfaces.i_engine_context import IEngineContext
from sagittarius_engine.runtime.scheduler.scheduler import ScheduledJob, Scheduler

logger = logging.getLogger("App.Alerting")

#: How often grouped alerts and the quiet-hours summary are looked at.
FLUSH_EVERY_SECONDS = 1


class AlertingModule(BoundedContextModule):
    """The outbox, the hub and the lanes that carry alerts to channels."""

    module_id = "alerting"

    #: Reads no other context's `contracts/` yet; `EPIC-036B` adds `bots` and `trading`.
    dependencies: list[str] = []  # noqa: RUF012 — the Engine reads a plain attribute

    _host: ThreadedDeliveryHost | None = None
    _job: ScheduledJob | None = None

    def register(self, context: IEngineContext) -> None:
        bind_alerting(context.container)

    def declare_operations(self, registry: IOperationsRegistry) -> None:
        """The alerting section of the health snapshot: is an alert stuck?"""
        registry.declare_health(
            HealthContributorDescriptor(
                SECTION_NAME,
                lambda resolver: AlertingHealthContributor(
                    resolver.resolve(IOutbox),  # type: ignore[type-abstract]
                    resolver.resolve(IAlertClock),  # type: ignore[type-abstract]
                ),
                self.module_id,
            )
        )

    def boot(self, context: IEngineContext) -> None:
        container = context.container
        if container.resolve(IInstanceAccess).read_only:
            logger.info("[alerting] not started: this copy is read-only")
            return
        hub = container.resolve(AlertHub)
        host = container.resolve(ThreadedDeliveryHost)
        host.start()
        self._host = host
        self._job = (
            container.resolve(Scheduler)
            .every(seconds=FLUSH_EVERY_SECONDS)
            .do(hub.flush_due)
        )

    def shutdown(self, context: IEngineContext) -> None:
        """Stop the lanes, then close the outbox: what is still queued stays in
        the file and goes out at the next start."""
        if self._job is not None:
            self._job.cancel()
            self._job = None
        if self._host is not None:
            self._host.stop()
            self._host = None
            context.container.resolve(IOutbox).close()
