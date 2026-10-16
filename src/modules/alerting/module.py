"""`alerting` - alerts reach the owner when the owner is away (`EPIC-036`, N1).

**The context's one question:** *when something the owner must know happens, how
does it reach them, once, even if a channel is down or the app restarts?* It
listens to `bots/contracts` (`EPIC-036G`; `EPIC-036B` adds `trading` and the
system); only `operations` reads it, through `alerting/contracts`, so a new kind
of bot changes nothing here.

What it holds (`EPIC-036A`, `EPIC-036G`; the design is `Docs/MODULES/alerting/`):

  - the typed `Alert`, `IAlertChannel` and the `AlertHub` that dedups, groups,
    inhibits, holds for quiet hours and routes;
  - a SQLite **outbox** under `<data root>/state/`, so an alert survives a restart
    and a dead network, and expires after 24 h instead of being sent late;
  - a **worker**, one lane per channel: priority, `retry_after`, bounded attempts,
    fail-over for CRITICAL, `CHANNEL_FAILING` when a channel gives up;
  - a health section: how many alerts wait and how long the oldest has;
  - the bot source: a bot entering HALTED or ERROR, or whose stop gave up, is one
    CRITICAL alert;
  - one channel, Discord, configured when its webhook is stored
    (`composition/channel_bindings.py` is where a channel is added);
  - `alert test`, the command-line Send test.

A read-only copy of the data root opens no outbox, starts no lane and subscribes
no source.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.bounded_context_module import (
    BoundedContextModule,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_registry import (
    CliCommandDescriptor,
    ICliRegistry,
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
from Sagittarius_Elite_Warrior.src.modules.alerting.application.alerting_health_contributor import (
    SECTION_NAME,
    AlertingHealthContributor,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.bot_alert_source import (
    BotAlertSource,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.cli.alert_cli_handler import (
    AlertCliHandler,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.composition.alerting_bindings import (
    bind_alerting,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_outbox import IOutbox
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_changed_event import (
    BotChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_stop_gave_up_event import (
    BotStopGaveUpEvent,
)
from sagittarius_engine.interfaces.i_engine_context import IEngineContext

logger = logging.getLogger("App.Alerting")


class AlertingModule(BoundedContextModule):
    """The outbox, the hub and the lanes that carry alerts to channels."""

    module_id = "alerting"

    #: Reads the bots' events and status report (`EPIC-036G`); `EPIC-036B` adds `trading`.
    dependencies: list[str] = ["bots"]  # noqa: RUF012 — the Engine reads a plain attribute

    _host: ThreadedDeliveryHost | None = None

    def register(self, context: IEngineContext) -> None:
        bind_alerting(context.container)

    def declare_cli(self, registry: ICliRegistry) -> None:
        """`alert test`: the Send test a headless host has instead of a page."""
        registry.declare(
            CliCommandDescriptor(
                name="alert", handler=AlertCliHandler, contributor_id=self.module_id
            )
        )

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
        host = container.resolve(ThreadedDeliveryHost)
        host.start()
        self._host = host
        # Subscribed before the seed: a change during the seed is then heard, and
        # the seed keeps a state a handler already recorded.
        source = container.resolve(BotAlertSource)
        bus = context.event_bus
        bus.on(BotChangedEvent, source.on_bot_changed)
        bus.on(BotStopGaveUpEvent, source.on_stop_gave_up)
        source.seed()

    def shutdown(self, context: IEngineContext) -> None:
        """Stop the lanes, then close the outbox: what is still queued stays in
        the file and goes out at the next start."""
        if self._host is not None:
            self._host.stop()
            self._host = None
            context.container.resolve(IOutbox).close()
