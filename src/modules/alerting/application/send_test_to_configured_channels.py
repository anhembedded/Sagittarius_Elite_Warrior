"""The Options page's Send test: `SendTestMessage` over the channels as configured now
(`EPIC-036D1`).

`alert test` runs in a process that has just booted, so the boot's catalog is the
truth. The Options page runs in a process that may have been booted before the owner
saved the webhook, and the run's catalog is fixed for its life
(`Docs/MODULES/alerting/05-building-blocks.md`): asking it would answer "nothing to
test" for a webhook that is saved. So the catalog is built again for each test, by the
same descriptors, and only the test message goes through it.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.alerting.application.send_test_message import (
    ChannelTestOutcome,
    SendTestMessage,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_channel_catalog_builder import (
    IChannelCatalogBuilder,
)


class SendTestToConfiguredChannels:
    def __init__(self, builder: IChannelCatalogBuilder, clock: IAlertClock) -> None:
        self._builder = builder
        self._clock = clock

    def run(self) -> tuple[ChannelTestOutcome, ...]:
        """One loud test message per channel configured now; empty when none is.
        Blocks on the network: call it off the UI thread."""
        return SendTestMessage(self._builder.build(), self._clock).run()
