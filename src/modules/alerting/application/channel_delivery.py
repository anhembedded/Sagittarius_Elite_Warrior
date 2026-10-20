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

#: How many waiting deliveries are looked at for a CRITICAL while the channel waits.
WAITING_SCAN = 20

#: Fail-overs remembered, so a long run does not grow the set without bound.
MAX_REMEMBERED = 1000


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
        self._horizon_read: set[str] = set()
        self._failing: set[str] = set()
        self._failed_over: dict[int, None] = {}

    def run_due(self, channel_id: str) -> int:
        """Try what is due on `channel_id`, most urgent first, until nothing is or
        the channel asks to wait; the number of tries made.

        A wait (`retry_after`, or the back-off after a failure) pauses the whole
        channel: a 429 answers for the channel, not for one message. A CRITICAL
        left waiting behind a wait longer than `failover_after` is queued on
        another channel at once.
        """
        self._outbox.expire_before(self._clock.now() - self._policy.expiry)
        tries = 0
        while True:
            now = self._clock.now()
            until = self._pause_until(channel_id)
            if until is not None and now < until:
                self._fail_over_waiting_criticals(channel_id, now, until - now)
                return tries
            due = self._outbox.due(channel_id, now, 1)
            if not due:
                return tries
            tries += 1
            if self._attempt(channel_id, due[0], now):
                return tries

    def _attempt(self, channel_id: str, item: DueDelivery, now: datetime) -> bool:
        """One try; whether the channel now has to wait.

        `attempts` counts real tries that did not work. An answer that only asks
        to wait (a 429) is the platform pacing us, not the channel failing: it
        does not use an attempt, and the 24 h expiry bounds how long we honour it.
        """
        result = self._call(channel_id, item)
        attempts = item.delivery.attempts
        if result.ok:
            self._outbox.mark(
                item.delivery.delivery_id,
                DeliveryUpdate(DeliveryState.SENT, attempts + 1, now, ""),
            )
            self._recovered(channel_id)
            return False
        if result.permanent:
            self._outbox.mark(
                item.delivery.delivery_id,
                DeliveryUpdate(DeliveryState.FAILED, attempts + 1, now, result.reason),
            )
            self._flag_failing(channel_id, result.reason)
            self._fail_over_once(channel_id, item)
            return False
        asked_to_wait = result.retry_after is not None
        if not asked_to_wait:
            attempts += 1
        wait = result.retry_after or self._policy.backoff_after(attempts)
        retry_at = now + wait
        exhausted = not asked_to_wait and attempts >= self._policy.max_attempts
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
            self._fail_over_once(channel_id, item)
        elif wait > self._policy.failover_after:
            self._fail_over_once(channel_id, item)
        return True

    def _fail_over_waiting_criticals(
        self, channel_id: str, now: datetime, remaining: timedelta
    ) -> None:
        if remaining <= self._policy.failover_after:
            return
        for waiting in self._outbox.due(channel_id, now, WAITING_SCAN):
            if waiting.alert.severity is not Severity.CRITICAL:
                return  # `due` lists CRITICAL first
            self._fail_over_once(channel_id, waiting)

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

    def _fail_over_once(self, channel_id: str, item: DueDelivery) -> None:
        """Queue a CRITICAL on another channel, once per delivery."""
        if item.alert.severity is not Severity.CRITICAL:
            return
        with self._lock:
            if item.delivery.delivery_id in self._failed_over:
                return
            self._failed_over[item.delivery.delivery_id] = None
            while len(self._failed_over) > MAX_REMEMBERED:
                del self._failed_over[next(iter(self._failed_over))]
        self._follow_up.fail_over(item.delivery.alert_id, channel_id)

    def pause_remaining(self, channel_id: str) -> timedelta | None:
        """How long the channel still waits; `None` when it does not. A lane sleeps no longer than
        this, so a pacing wait of a fraction of a second is not stretched to a poll interval."""
        until = self._pause_until(channel_id)
        if until is None:
            return None
        remaining = until - self._clock.now()
        return remaining if remaining > timedelta(0) else None

    def _pause_until(self, channel_id: str) -> datetime | None:
        """When the channel may be tried again. After a restart the in-memory wait
        is gone, so the first look reads it back from the channel's open
        `RETRYING` rows: a restart does not cancel a 10 minute `retry_after`."""
        with self._lock:
            first_look = channel_id not in self._horizon_read
            self._horizon_read.add(channel_id)
        if first_look:
            horizon = self._outbox.retry_horizon(channel_id)
            if horizon is not None:
                self._pause(channel_id, horizon)
        with self._lock:
            return self._paused_until.get(channel_id)

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
