"""The alerting world a test builds: a real outbox, fake channels, a fake clock.

Nothing here is a double of the code under test: the hub, the router, the
worker pass and the SQLite outbox are the real ones (`testing-rule.md` §2, a
double's shape comes from the interface). Only the channels (the network
boundary) and the clock are fakes.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.memory_alert_settings import (
    InMemoryAlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.registered_channel_catalog import (
    RegisteredChannelCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.sqlite_outbox import (
    SqliteOutbox,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.alert_hub import (
    AlertHub,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.channel_delivery import (
    ChannelDelivery,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_channel import (
    IAlertChannel,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_delivery_wakeup import (
    IDeliveryWakeup,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_channel import (
    FakeAlertChannel,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_clock import (
    FAKE_CLOCK_START,
    FakeAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_policies import (
    DeliveryPolicy,
    NoisePolicy,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.delivery_state import (
    DeliveryState,
)

NOW = FAKE_CLOCK_START
SPOT = "spot-mainnet"


def bot_subject(
    bot_id: str = "g3n092", venue: str = SPOT, symbol: str = "ETHUSDT"
) -> AlertSubject:
    return AlertSubject.bot(bot_id, f"bot {bot_id}", "spot-grid", venue, symbol)


def an_alert(
    kind: AlertKind = AlertKind.BOT_HALTED,
    subject: AlertSubject | None = None,
    at: datetime = NOW,
    reason: str = "",
) -> Alert:
    return Alert.raised(
        kind, subject or bot_subject(), f"{kind.name} title", "detail", at, reason
    )


class CountingWakeup(IDeliveryWakeup):
    """Counts how often the hub asked the worker to look at the outbox."""

    def __init__(self) -> None:
        self.calls = 0

    def notify(self) -> None:
        self.calls += 1


@dataclass
class Rig:
    """Hub + worker pass + outbox over named fake channels."""

    clock: FakeAlertClock
    outbox: SqliteOutbox
    channels: dict[str, IAlertChannel]
    settings: InMemoryAlertSettings
    hub: AlertHub
    delivery: ChannelDelivery
    wakeup: CountingWakeup
    path: Path
    _extra: list[object] = field(default_factory=list)

    def deliver_all(self) -> None:
        """One worker pass over every channel, as the lanes do."""
        for channel_id in self.channels:
            self.delivery.run_due(channel_id)

    def received_kinds(self, channel_id: str) -> list[AlertKind]:
        channel = self.channels[channel_id]
        assert isinstance(channel, FakeAlertChannel)
        return [item.alert.kind for item in channel.received]


def build_rig(
    tmp_path: Path,
    channel_ids: Iterable[str] = ("phone", "backup"),
    delivery_policy: DeliveryPolicy | None = None,
    noise_policy: NoisePolicy | None = None,
    clock: FakeAlertClock | None = None,
    outbox: SqliteOutbox | None = None,
    wakeup: IDeliveryWakeup | None = None,
    channel_map: Mapping[str, IAlertChannel] | None = None,
) -> Rig:
    the_clock = clock or FakeAlertClock()
    path = tmp_path / "state" / "alerts.sqlite3"
    the_outbox = outbox or SqliteOutbox(path)
    channels: dict[str, IAlertChannel] = (
        dict(channel_map)
        if channel_map is not None
        else {channel_id: FakeAlertChannel() for channel_id in channel_ids}
    )
    catalog = RegisteredChannelCatalog(channels)
    settings = InMemoryAlertSettings()
    counting = CountingWakeup()
    policy = delivery_policy or DeliveryPolicy()
    hub = AlertHub(
        the_outbox,
        catalog,
        settings,
        the_clock,
        wakeup or counting,
        noise_policy or NoisePolicy(),
        policy,
    )
    delivery = ChannelDelivery(the_outbox, catalog, the_clock, hub, policy)
    return Rig(the_clock, the_outbox, channels, settings, hub, delivery, counting, path)


def minutes(count: float) -> timedelta:
    return timedelta(minutes=count)


def at_utc(hour: int, minute: int = 0) -> datetime:
    return datetime(NOW.year, NOW.month, NOW.day, hour, minute, tzinfo=UTC)


#: A policy that gives up after three real failures, quickly.
FAST = DeliveryPolicy(max_attempts=3, backoff_base=timedelta(seconds=1))


def states_of(rig: Rig, channel_id: str) -> list[DeliveryState]:
    """The state of every delivery the channel holds, newest alert first."""
    return [
        d.state
        for entry in rig.outbox.history(50)
        for d in entry.deliveries
        if d.channel_id == channel_id
    ]
