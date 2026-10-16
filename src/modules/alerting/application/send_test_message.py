"""The Send test: one test message to each configured channel, now (`EPIC-036G`).

Design 036 §9's Send test calls the channel directly, not through the hub and
the outbox: the owner is asking "does this channel reach me?" and wants the
answer while waiting, and a second process (`alert test` beside a running host)
is a read-only copy that may not write the outbox (`EPIC-035H`). So nothing here
is stored, deduplicated or retried; the answer is the channel's own
`DeliveryResult`, whose reason never carries a secret.

The test message is loud: a silent one would prove nothing about the push the
owner relies on.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.delivery_result import (
    DeliveryResult,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_channel_catalog import (
    IAlertChannelCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness

TEST_TITLE = "Test message from Sagittarius Elite Warrior"
TEST_DETAIL = (
    "If you can read this, a halted bot reaches you here. "
    "A message in this channel is not proof that a bot has trouble: check the app."
)


@dataclass(frozen=True, slots=True)
class ChannelTestOutcome:
    channel_id: str
    result: DeliveryResult


class SendTestMessage:
    def __init__(self, catalog: IAlertChannelCatalog, clock: IAlertClock) -> None:
        self._catalog = catalog
        self._clock = clock

    def run(self) -> tuple[ChannelTestOutcome, ...]:
        """One loud test message per configured channel; empty when there is none."""
        alert = Alert.raised(
            AlertKind.TEST,
            AlertSubject.app(),
            TEST_TITLE,
            TEST_DETAIL,
            self._clock.now(),
            reason=self._clock.now().isoformat(),
        )
        return tuple(
            ChannelTestOutcome(
                channel_id,
                self._catalog.channel(channel_id).deliver(alert, Loudness.LOUD),
            )
            for channel_id in self._catalog.channel_ids()
        )
