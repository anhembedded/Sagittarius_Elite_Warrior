"""`EPIC-036D1` — the Options page's Send test asks the channels as configured *now*,
not as they were at boot, so a webhook saved a moment ago can be tested without a restart."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.registered_channel_catalog import (
    RegisteredChannelCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.send_test_to_configured_channels import (
    SendTestToConfiguredChannels,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.delivery_result import (
    DeliveryResult,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_channel_catalog import (
    IAlertChannelCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_channel_catalog_builder import (
    IChannelCatalogBuilder,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_channel import (
    FakeAlertChannel,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_clock import (
    FakeAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness


class _Builder(IChannelCatalogBuilder):
    def __init__(self, catalog: IAlertChannelCatalog) -> None:
        self.catalog = catalog
        self.builds = 0

    def build(self) -> IAlertChannelCatalog:
        self.builds += 1
        return self.catalog


def test_it_sends_one_loud_test_alert_to_each_channel_the_builder_returns() -> None:
    channel = FakeAlertChannel()
    builder = _Builder(RegisteredChannelCatalog({"discord": channel}))

    outcomes = SendTestToConfiguredChannels(builder, FakeAlertClock()).run()

    assert [(o.channel_id, o.result.ok) for o in outcomes] == [("discord", True)]
    [received] = channel.received
    assert received.alert.kind is AlertKind.TEST
    assert received.loudness is Loudness.LOUD


def test_it_builds_the_catalog_again_on_every_run() -> None:
    builder = _Builder(RegisteredChannelCatalog({}))
    sender = SendTestToConfiguredChannels(builder, FakeAlertClock())

    first = sender.run()
    second = sender.run()

    assert (first, second) == ((), ())
    assert builder.builds == 2


def test_a_channel_that_refuses_is_reported_with_its_own_reason() -> None:
    refusing = FakeAlertChannel(
        default=DeliveryResult.refused("Discord refused the webhook message (404)")
    )
    builder = _Builder(RegisteredChannelCatalog({"discord": refusing}))

    [outcome] = SendTestToConfiguredChannels(builder, FakeAlertClock()).run()

    assert not outcome.result.ok
    assert outcome.result.reason == "Discord refused the webhook message (404)"
