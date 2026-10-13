"""Binds the alerting ports to their adapters (`BoundedContextModule.register`).

Only lambdas and instances with no I/O: the outbox file is opened on first
`resolve`, and `boot()` is what resolves it - never in a read-only copy.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.core.repo_root import data_root
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.memory_alert_settings import (
    InMemoryAlertSettings,
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
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.threaded_delivery_host import (
    ThreadedDeliveryHost,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.wake_signal import (
    WakeSignal,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.alert_hub import (
    AlertHub,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.channel_delivery import (
    ChannelDelivery,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.composition.channel_bindings import (
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
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_delivery_wakeup import (
    IDeliveryWakeup,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_outbox import IOutbox
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_policies import (
    DeliveryPolicy,
    NoisePolicy,
)
from sagittarius_engine.interfaces.i_container import IContainer

#: How often a lane looks at the outbox when nobody nudged it: what picks up a
#: `retry_after` that has come due.
LANE_POLL_SECONDS = 5.0


def outbox_path() -> Path:
    return data_root() / "state" / "alerts.sqlite3"


def bind_alerting(container: IContainer) -> None:
    container.singleton(IAlertClock, SystemAlertClock())
    container.singleton(IAlertSettingsSource, InMemoryAlertSettings())
    container.singleton(WakeSignal, WakeSignal())
    container.singleton(IDeliveryWakeup, lambda resolver: resolver.resolve(WakeSignal))
    container.singleton(IAlertChannelCatalog, build_channel_catalog)
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
        ChannelDelivery,
        lambda resolver: ChannelDelivery(
            resolver.resolve(IOutbox),
            resolver.resolve(IAlertChannelCatalog),
            resolver.resolve(IAlertClock),
            resolver.resolve(AlertHub),
            resolver.resolve(DeliveryPolicy),
        ),
    )
    container.singleton(
        ThreadedDeliveryHost,
        lambda resolver: ThreadedDeliveryHost(
            resolver.resolve(ChannelDelivery),
            resolver.resolve(IAlertChannelCatalog).channel_ids(),
            resolver.resolve(WakeSignal),
            LANE_POLL_SECONDS,
        ),
    )
