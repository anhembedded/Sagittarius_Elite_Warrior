"""Retry failed: the owner asks for every delivery that gave up to be tried again (`EPIC-036D5`).

A delivery is `FAILED` when its channel refused it for good or its tries ran out. Fixing the
cause (a webhook saved again, a bot added to the chat) does not send it by itself, so the Alerts
screen offers this. It puts those deliveries back to `PENDING`, due now; the channel's lane picks
them up at its next look (`LANE_POLL_SECONDS`), at its own pace and under its own rate limit, and
an outcome appears in the history as for any delivery. An alert older than the expiry is not sent
late (N2), so it is left alone. A stored alert is not raised again, so nothing is deduplicated or
counted twice.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_delivery_requeue import (
    IDeliveryRequeue,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_policies import (
    DeliveryPolicy,
)

logger = logging.getLogger("App.Alerting")


class RetryFailedDeliveries:
    def __init__(
        self, requeue: IDeliveryRequeue, clock: IAlertClock, policy: DeliveryPolicy
    ) -> None:
        self._requeue = requeue
        self._clock = clock
        self._policy = policy

    def run(self) -> int:
        """How many failed deliveries were queued again."""
        now = self._clock.now()
        count = self._requeue.requeue_failed(now - self._policy.expiry, now)
        logger.info("[alert-retry] %d failed delivery(ies) queued again", count)
        return count
