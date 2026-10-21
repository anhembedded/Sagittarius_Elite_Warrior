"""What the Alerts screen reads and does (`EPIC-036D2`, `EPIC-036D5`): the history read model
and Retry failed. Split from `alerting_bindings.py`, which is at the file-size ceiling."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.sqlite_delivery_requeue import (
    SqliteDeliveryRequeue,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.outbox_alert_history import (
    OutboxAlertHistory,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.retry_failed_deliveries import (
    RetryFailedDeliveries,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_channel_catalog import (
    IAlertChannelCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_history import (
    IAlertHistory,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_delivery_requeue import (
    IDeliveryRequeue,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_outbox import IOutbox
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_policies import (
    DeliveryPolicy,
)
from sagittarius_engine.interfaces.i_container import IContainer


def bind_history(container: IContainer, outbox_path: Callable[[], Path]) -> None:
    container.singleton(
        IAlertHistory,
        lambda resolver: OutboxAlertHistory(
            resolver.resolve(IOutbox), resolver.resolve(IAlertChannelCatalog)
        ),
    )
    container.singleton(
        IDeliveryRequeue, lambda _resolver: SqliteDeliveryRequeue(outbox_path())
    )
    container.singleton(
        RetryFailedDeliveries,
        lambda resolver: RetryFailedDeliveries(
            resolver.resolve(IDeliveryRequeue),
            resolver.resolve(IAlertClock),
            resolver.resolve(DeliveryPolicy),
        ),
    )
