"""`alerting` - alerts reach the owner when the owner is away (`EPIC-036`, N1).

**The context's one question:** *when something the owner must know happens, how
does it reach them, once, even if a channel is down or the app restarts?* It
listens to `bots/contracts` (`EPIC-036G`), `trading`'s stream health (`EPIC-036B1`)
and, with `EPIC-036B`, the system; only `operations` reads it, through `alerting/contracts`, so a new kind
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
    CRITICAL alert, and so are a stop loss or take profit that ran and a bot closing at a range
    exit (a price outside the range of a bot that holds is a WARNING); a rate limit, a rejected
    key, a storage pause and a wait stalled on a quiet price feed are kinds of their own
    (`EPIC-036B2`, `application/sources/bot_reason_routes.py`);
  - early warnings (`EPIC-036B1`): a Futures bot inside its liquidation warning distance
    (`LIQUIDATION_RISK`) and a venue's user-data stream down past a grace (`USER_STREAM_DOWN`),
    each once per condition with a cool-down;
  - the heartbeat every six hours and the daily summary (`EPIC-036E`), sent from the housekeeping
    thread out of the bots' status report;
  - the fill source (`BOT-189`): one INFO, silent message for every order that filled whole, the
    cycle's profit on the fill that closes a cycle, bounded per channel by `FillBacklog`;
  - Telegram beside it (`EPIC-036C1`), configured when its bot token and chat id are stored, with
    the old config-file token moved into the secret store at boot;
  - one channel, Discord, configured when its webhook is stored
    (`composition/channel_bindings.py` is where a channel is added);
  - `alert test`, the command-line Send test;
  - Tools → Options → Alerts: the Discord webhook, Save, Remove and Send test
    (`EPIC-036D1`; `ui/options/`).

A read-only copy of the data root opens no outbox, starts no lane and subscribes
no source.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.bounded_context_module import (
    BoundedContextModule,
)
from Sagittarius_Elite_Warrior.src.core.contracts.deferred import Deferred
from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_registry import (
    CliCommandDescriptor,
    ICliRegistry,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_contribution_registry import (
    IContributionRegistry,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_operations_registry import (
    HealthContributorDescriptor,
    IOperationsRegistry,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_options_section import (
    IOptionsSection,
)
from Sagittarius_Elite_Warrior.src.core.contracts.options_page_contribution import (
    OptionsPageContribution,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.threaded_delivery_host import (
    ThreadedDeliveryHost,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.alerting_health_contributor import (
    SECTION_NAME,
    AlertingHealthContributor,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.account_alert_source import (
    AccountAlertSource,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.bot_alert_source import (
    BotAlertSource,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.bot_exit_alert_source import (
    BotExitAlertSource,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.bot_fill_alert_source import (
    BotFillAlertSource,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.liquidation_alert_source import (
    LiquidationAlertSource,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.stream_alert_source import (
    StreamAlertSource,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.telegram_config_migration import (
    TelegramConfigMigration,
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
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.history.alerts_screen import (
    alerts_screen,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.account_loss_cap_tripped_event import (
    AccountLossCapTrippedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_auto_recovered_event import (
    BotAutoRecoveredEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_changed_event import (
    BotChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_exit_closed_event import (
    BotExitClosedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_order_filled_event import (
    BotOrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_protective_stop_event import (
    BotProtectiveStopEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_range_changed_event import (
    BotRangeChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_range_entered_event import (
    BotRangeEnteredEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_recovery_stalled_event import (
    BotRecoveryStalledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_risk_changed_event import (
    BotRiskChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_stop_gave_up_event import (
    BotStopGaveUpEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.user_stream_health_event import (
    UserStreamHealthEvent,
)
from sagittarius_engine.interfaces.i_engine_context import IEngineContext

logger = logging.getLogger("App.Alerting")

#: Tools → Options → Alerts (`EPIC-036D1`), built when the shell assembles the dialog's pages.
_OPTIONS_PAGE: Deferred[IOptionsSection] = Deferred(
    "Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.alerts_options_page"
    ":build_alerts_options_page"
)


class AlertingModule(BoundedContextModule):
    """The outbox, the hub and the lanes that carry alerts to channels."""

    module_id = "alerting"

    #: Reads the bots' events and status report (`EPIC-036G`) and `trading`'s stream health
    #: (`EPIC-036B1`).
    dependencies: list[str] = ["bots", "trading"]  # noqa: RUF012 — the Engine reads a plain attribute

    _host: ThreadedDeliveryHost | None = None

    def register(self, context: IEngineContext) -> None:
        bind_alerting(context.container)

    def contribute(self, registry: IContributionRegistry) -> None:
        """The Alerts page of Tools → Options: the Discord webhook and its Send test
        (`EPIC-036D1`), and the Alerts screen: what was sent (`EPIC-036D2`). Both are
        `Deferred`, so no widget module is imported at boot."""
        registry.contribute_options_page(
            OptionsPageContribution(
                contributor_id=self.module_id, order=30, factory=_OPTIONS_PAGE
            )
        )
        registry.contribute_screen(alerts_screen())

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
        # Before the host builds the channel catalog: a token moved out of the config file
        # is then the one the Telegram channel finds (`EPIC-036C1`).
        container.resolve(TelegramConfigMigration).run()
        host = container.resolve(ThreadedDeliveryHost)
        host.start()
        self._host = host
        # Subscribed before the seed: a change during the seed is then heard, and
        # the seed keeps a state a handler already recorded.
        source = container.resolve(BotAlertSource)
        bus = context.event_bus
        bus.on(BotChangedEvent, source.on_bot_changed)
        bus.on(BotStopGaveUpEvent, source.on_stop_gave_up)
        bus.on(BotRecoveryStalledEvent, source.on_recovery_stalled)
        bus.on(
            AccountLossCapTrippedEvent,
            container.resolve(AccountAlertSource).on_account_loss_cap_tripped,
        )
        bus.on(BotAutoRecoveredEvent, source.on_auto_recovered)
        bus.on(BotRangeChangedEvent, source.on_range_changed)
        bus.on(BotRangeEnteredEvent, source.on_range_entered)
        bus.on(BotProtectiveStopEvent, source.on_protective_stop)
        liquidation = container.resolve(LiquidationAlertSource)
        bus.on(BotRiskChangedEvent, liquidation.on_risk_changed)
        bus.on(BotChangedEvent, liquidation.on_bot_changed)
        bus.on(
            UserStreamHealthEvent,
            container.resolve(StreamAlertSource).on_user_stream_health,
        )
        bus.on(
            BotOrderFilledEvent, container.resolve(BotFillAlertSource).on_order_filled
        )
        bus.on(BotExitClosedEvent, container.resolve(BotExitAlertSource).on_exit_closed)
        source.seed()

    def shutdown(self, context: IEngineContext) -> None:
        """Stop the lanes, then close the outbox: what is still queued stays in
        the file and goes out at the next start."""
        if self._host is not None:
            self._host.stop()
            self._host = None
            context.container.resolve(IOutbox).close()
