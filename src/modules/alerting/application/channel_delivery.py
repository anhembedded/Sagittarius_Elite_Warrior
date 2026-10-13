"""One worker pass over one channel's queue (design §6, §8).

`run_due` is the whole behaviour and takes no thread: the clock is injected and
nothing sleeps, so a test drives it. `ThreadedDeliveryHost` runs it on a lane per
channel, so a slow channel delays no other.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.delivery_result import (
    DeliveryResult,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_channel_catalog import (
    IAlertChannelCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_delivery_follow_up import (
    IDeliveryFollowUp,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_outbox import IOutbox
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.outbox_records import (
    DeliveryUpdate,
    DueDelivery,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_policies import (
    DeliveryPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.delivery_state import (
    DeliveryState,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity

logger = logging.getLogger("App.Alerting")


class ChannelDelivery:
    def __init__(
        self,
        outbox: IOutbox,
        catalog: IAlertChannelCatalog,
        clock: IAlertClock,
        follow_up: IDeliveryFollowUp,
        policy: DeliveryPolicy,
    ) -> None:
        self._outbox = outbox
        self._catalog = catalog
        self._clock = clock
        self._follow_up = follow_up
        self._policy = policy
        self._lock = threading.Lock()
        self._paused_until: dict[str, datetime] = {}
        self._failing: set[str] = set()
        self._failed_over: set[int] = set()

    def run_due(self, channel_id: str) -> int:
        """Try what is due on `channel_id`, most urgent first, until nothing is or
        the channel asks to wait; the number of tries made.

        A wait (`retry_after`, or the back-off after a failure) pauses the whole
        channel: a 429 answers for the channel, not for one message.
        """
        self._outbox.expire_before(self._clock.now() - self._policy.expiry)
        tries = 0
        while True:
            now = self._clock.now()
            if self._is_paused(channel_id, now):
                return tries
            due = self._outbox.due(channel_id, now, 1)
            if not due:
                return tries
            tries += 1
            if self._attempt(channel_id, due[0], now):
                return tries

    def _attempt(self, channel_id: str, item: DueDelivery, now: datetime) -> bool:
        """One try; whether the channel now has to wait."""
        result = self._call(channel_id, item)
        attempts = item.delivery.attempts + 1
        if result.ok:
            self._outbox.mark(
                item.delivery.delivery_id,
                DeliveryUpdate(DeliveryState.SENT, attempts, now, ""),
            )
            self._recovered(channel_id)
            return False
        if result.permanent:
            self._outbox.mark(
                item.delivery.delivery_id,
                DeliveryUpdate(DeliveryState.FAILED, attempts, now, result.reason),
            )
            self._flag_failing(channel_id, result.reason)
            return False
        wait = result.retry_after or self._policy.backoff_after(attempts)
        retry_at = now + wait
        exhausted = attempts >= self._policy.max_attempts
        self._outbox.mark(
            item.delivery.delivery_id,
            DeliveryUpdate(
                DeliveryState.FAILED if exhausted else DeliveryState.RETRYING,
                attempts,
                retry_at,
                result.reason,
            ),
        )
        self._pause(channel_id, retry_at)
        if exhausted:
            self._flag_failing(channel_id, result.reason)
        elif self._should_fail_over(item, wait):
            self._follow_up.fail_over(item.delivery.alert_id, channel_id)
        return True

    def _call(self, channel_id: str, item: DueDelivery) -> DeliveryResult:
        channel = self._catalog.channel(channel_id)
        try:
            return channel.deliver(item.alert, item.delivery.loudness)
        except Exception as error:  # noqa: BLE001 — a channel must not raise; containing one that does is this method's job
            # Only the type: the message of a transport error can carry the
            # webhook URL or the token.
            logger.warning(
                "[alert-channel] %s raised %s", channel_id, type(error).__name__
            )
            return DeliveryResult.failed(f"channel raised {type(error).__name__}")

    def _should_fail_over(self, item: DueDelivery, wait: timedelta) -> bool:
        if item.alert.severity is not Severity.CRITICAL:
            return False
        if wait <= self._policy.failover_after:
            return False
        with self._lock:
            if item.delivery.delivery_id in self._failed_over:
                return False
            self._failed_over.add(item.delivery.delivery_id)
        return True

    def _is_paused(self, channel_id: str, now: datetime) -> bool:
        with self._lock:
            until = self._paused_until.get(channel_id)
        return until is not None and now < until

    def _pause(self, channel_id: str, until: datetime) -> None:
        with self._lock:
            self._paused_until[channel_id] = until

    def _flag_failing(self, channel_id: str, reason: str) -> None:
        with self._lock:
            if channel_id in self._failing:
                return
            self._failing.add(channel_id)
        logger.warning("[alert-channel] %s is failing: %s", channel_id, reason)
        self._follow_up.channel_failing(channel_id, reason)

    def _recovered(self, channel_id: str) -> None:
        with self._lock:
            was_failing = channel_id in self._failing
            self._failing.discard(channel_id)
        if was_failing:
            logger.info("[alert-channel] %s delivers again", channel_id)
