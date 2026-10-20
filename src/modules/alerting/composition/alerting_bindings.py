"""Binds the alerting ports to their adapters (`BoundedContextModule.register`).

Only lambdas and instances with no I/O: the outbox file is opened on first
`resolve`, and `boot()` is what resolves it - never in a read-only copy.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_reader import IConfigReader
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_writer import IConfigWriter
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.core.repo_root import data_root
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.discord_message import (
    is_discord_webhook_url,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.discord_webhook_channel import (
    DISCORD_CHANNEL_ID,
    DISCORD_WEBHOOK_SECRET,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.json_alert_settings import (
    JsonAlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.null_alert_publisher import (
    NullAlertPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.sqlite_outbox import (
    SqliteOutbox,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.system_alert_clock import (
    SystemAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.telegram_channel import (
    TELEGRAM_CHAT_SECRET,
    TELEGRAM_TOKEN_SECRET,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.threaded_delivery_host import (
    ThreadedDeliveryHost,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.urllib_webhook_transport import (
    UrllibWebhookTransport,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.wake_signal import (
    WakeSignal,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.worker_liveness import (
    WorkerLiveness,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.alert_hub import (
    AlertHub,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.channel_alerting_status import (
    ChannelAlertingStatus,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.channel_delivery import (
    ChannelDelivery,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.dead_mans_switch import (
    DeadMansSwitch,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.discord_webhook_setup import (
    DiscordWebhookSetup,
    WebhookChannelSpec,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.heartbeat_service import (
    HeartbeatService,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.send_test_to_configured_channels import (
    SendTestToConfiguredChannels,
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
from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.system_alert_source import (
    SystemAlertSource,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.telegram_config_migration import (
    TelegramConfigMigration,
    TelegramSecretNames,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.composition.channel_bindings import (
    ChannelSecrets,
    DescriptorChannelCatalogBuilder,
    build_channel_catalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_channel_catalog import (
    IAlertChannelCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_publisher import (
    IAlertPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_settings_source import (
    IAlertSettingsSource,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alerting_status import (
    IAlertingStatus,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_bot_alert_modes import (
    IBotAlertModes,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_channel_catalog_builder import (
    IChannelCatalogBuilder,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_delivery_wakeup import (
    IDeliveryWakeup,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_outbox import IOutbox
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_system_failure_reporter import (
    ISystemFailureReporter,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_webhook_transport import (
    IWebhookTransport,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_worker_liveness import (
    IWorkerLiveness,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_policies import (
    DeliveryPolicy,
    NoisePolicy,
)
from Sagittarius_Elite_Warrior.src.support.secrets.secret_store_order import (
    build_secret_stores,
)
from sagittarius_engine.interfaces.i_container import IContainer

#: How often a lane looks at the outbox when nobody nudged it: what picks up a
#: `retry_after` that has come due.
LANE_POLL_SECONDS = 5.0

#: How often grouped alerts and the quiet-hours summary are looked at.
HOUSEKEEPING_SECONDS = 1.0

#: How often the beacon asks the dead man's switch whether a ping is due (it does no
#: I/O unless one is).
BEACON_SECONDS = 5.0


def _housekeeping_of(
    heartbeat: Callable[[], None], flush: Callable[[], None]
) -> Callable[[], None]:
    """One housekeeping pass: the schedule first (`EPIC-036E`), so a failing flush cannot hold a
    heartbeat back, then the hub's flush."""

    def run() -> None:
        heartbeat()
        flush()

    return run


def outbox_path() -> Path:
    return data_root() / "state" / "alerts.sqlite3"


def alert_settings_path() -> Path:
    return data_root() / "state" / "alert_settings.json"


def bind_alerting(container: IContainer) -> None:
    container.singleton(IAlertClock, SystemAlertClock())
    # `BOT-191`: what the owner set per bot survives a restart; a missing or unreadable file
    # is every default. One object serves the hub's reads and the Options page's edits.
    container.singleton(
        JsonAlertSettings,
        lambda resolver: JsonAlertSettings(
            alert_settings_path(), read_only=resolver.resolve(IInstanceAccess).read_only
        ),
    )
    container.singleton(
        IAlertSettingsSource, lambda resolver: resolver.resolve(JsonAlertSettings)
    )
    container.singleton(
        IBotAlertModes, lambda resolver: resolver.resolve(JsonAlertSettings)
    )
    container.singleton(WakeSignal, WakeSignal())
    container.singleton(IDeliveryWakeup, lambda resolver: resolver.resolve(WakeSignal))
    # `EPIC-036G` (D3): the channels' secrets come from the stores the mainnet keys
    # use, in their order; built when the catalog is first built, never here.
    container.singleton(
        ChannelSecrets, lambda _resolver: ChannelSecrets(build_secret_stores())
    )
    container.singleton(IWebhookTransport, UrllibWebhookTransport())
    container.singleton(IAlertChannelCatalog, build_channel_catalog)
    container.singleton(
        IAlertingStatus,
        lambda resolver: ChannelAlertingStatus(
            resolver.resolve(IAlertChannelCatalog),
            resolver.resolve(IAlertSettingsSource),
        ),
    )
    # `EPIC-036D1`: the Options page's Save, Remove and Send test. The setup reads and
    # writes the same stores the channel reads; the test builds a catalog afresh.
    container.singleton(
        IChannelCatalogBuilder,
        lambda resolver: DescriptorChannelCatalogBuilder(resolver),
    )
    container.singleton(
        DiscordWebhookSetup,
        lambda resolver: DiscordWebhookSetup(
            resolver.resolve(ChannelSecrets).store,
            WebhookChannelSpec(
                DISCORD_CHANNEL_ID, DISCORD_WEBHOOK_SECRET, is_discord_webhook_url
            ),
            resolver.resolve(IAlertChannelCatalog),
        ),
    )
    container.singleton(
        SendTestToConfiguredChannels,
        lambda resolver: SendTestToConfiguredChannels(
            resolver.resolve(IChannelCatalogBuilder),
            resolver.resolve(IAlertClock),
        ),
    )
    container.singleton(IOutbox, lambda _resolver: SqliteOutbox(outbox_path()))
    container.singleton(DeliveryPolicy, DeliveryPolicy())
    container.singleton(NoisePolicy, NoisePolicy())
    container.singleton(
        AlertHub,
        lambda resolver: AlertHub(
            resolver.resolve(IOutbox),
            resolver.resolve(IAlertChannelCatalog),
            resolver.resolve(IAlertSettingsSource),
            resolver.resolve(IAlertClock),
            resolver.resolve(IDeliveryWakeup),
            resolver.resolve(NoisePolicy),
            resolver.resolve(DeliveryPolicy),
        ),
    )
    container.singleton(
        IAlertPublisher,
        lambda resolver: (
            NullAlertPublisher()
            if resolver.resolve(IInstanceAccess).read_only
            else resolver.resolve(AlertHub)
        ),
    )
    container.singleton(
        BotAlertSource,
        lambda resolver: BotAlertSource(
            resolver.resolve(ICommandDispatcher),
            resolver.resolve(IAlertPublisher),
            resolver.resolve(IAlertClock),
        ),
    )
    container.singleton(
        LiquidationAlertSource,
        lambda resolver: LiquidationAlertSource(
            resolver.resolve(ICommandDispatcher),
            resolver.resolve(IAlertPublisher),
            resolver.resolve(IAlertClock),
        ),
    )
    container.singleton(
        StreamAlertSource,
        lambda resolver: StreamAlertSource(
            resolver.resolve(IAlertPublisher), resolver.resolve(IAlertClock)
        ),
    )
    container.singleton(
        ISystemFailureReporter,
        lambda resolver: SystemAlertSource(
            resolver.resolve(IAlertPublisher), resolver.resolve(IAlertClock)
        ),
    )
    container.singleton(
        BotFillAlertSource,
        lambda resolver: BotFillAlertSource(
            resolver.resolve(ICommandDispatcher),
            resolver.resolve(IAlertPublisher),
            resolver.resolve(IAlertClock),
        ),
    )
    container.singleton(
        BotExitAlertSource,
        lambda resolver: BotExitAlertSource(
            resolver.resolve(ICommandDispatcher),
            resolver.resolve(IAlertPublisher),
            resolver.resolve(IAlertClock),
        ),
    )
    container.singleton(
        ChannelDelivery,
        lambda resolver: ChannelDelivery(
            resolver.resolve(IOutbox),
            resolver.resolve(IAlertChannelCatalog),
            resolver.resolve(IAlertClock),
            resolver.resolve(AlertHub),
            resolver.resolve(DeliveryPolicy),
        ),
    )
    # `EPIC-036E1`: the dead man's switch pings while the worker's stamps are fresh.
    container.singleton(
        WorkerLiveness, lambda resolver: WorkerLiveness(resolver.resolve(IAlertClock))
    )
    container.singleton(
        IWorkerLiveness, lambda resolver: resolver.resolve(WorkerLiveness)
    )
    container.singleton(
        DeadMansSwitch,
        lambda resolver: DeadMansSwitch(
            resolver.resolve(ChannelSecrets).store,
            resolver.resolve(IWebhookTransport),
            resolver.resolve(IAlertClock),
            resolver.resolve(IWorkerLiveness),
            resolver.resolve(AlertHub),
        ),
    )
    container.singleton(
        TelegramConfigMigration,
        lambda resolver: TelegramConfigMigration(
            resolver.resolve(IConfigReader),
            resolver.resolve(IConfigWriter),
            resolver.resolve(ChannelSecrets).store,
            TelegramSecretNames(TELEGRAM_TOKEN_SECRET, TELEGRAM_CHAT_SECRET),
        ),
    )
    container.singleton(
        HeartbeatService,
        lambda resolver: HeartbeatService(
            resolver.resolve(ICommandDispatcher),
            resolver.resolve(IAlertPublisher),
            resolver.resolve(IOutbox),
            resolver.resolve(IAlertClock),
        ),
    )
    container.singleton(
        ThreadedDeliveryHost,
        lambda resolver: ThreadedDeliveryHost(
            resolver.resolve(ChannelDelivery),
            resolver.resolve(IAlertChannelCatalog).channel_ids(),
            resolver.resolve(WakeSignal),
            LANE_POLL_SECONDS,
            _housekeeping_of(
                resolver.resolve(HeartbeatService).tick,
                resolver.resolve(AlertHub).flush_due,
            ),
            HOUSEKEEPING_SECONDS,
            resolver.resolve(WorkerLiveness),
            resolver.resolve(DeadMansSwitch).tick,
            BEACON_SECONDS,
        ),
    )
