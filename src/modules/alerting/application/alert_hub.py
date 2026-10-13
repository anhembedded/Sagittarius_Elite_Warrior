"""The hub: what a source hands over becomes, at most, one stored alert (design §4).

`publish` runs on the caller's thread and only writes the outbox: no channel is
called here, so a failing, slow or rate-limited channel cannot hold a bot or the
UI. Everything past it - sending, retrying, failing over - is the worker's.

In order, an alert is: **inhibited** (a venue-down alert hides its bots' feed
alerts), **deduplicated** (a repeat in the window counts on one record), **held**
(INFO and WARNING in quiet hours), **grouped** (one kind and venue in a short
window), then **routed** and stored.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.alerting.application.alert_coalescer import (
    AlertCoalescer,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.alert_deduplicator import (
    AlertDeduplicator,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.alert_router import (
    AlertRouter,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.condition_book import (
    ConditionBook,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.delivery_admission import (
    DeliveryAdmission,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.quiet_hours_hold import (
    QuietHoursHold,
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
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_delivery_follow_up import (
    IDeliveryFollowUp,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_delivery_wakeup import (
    IDeliveryWakeup,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_outbox import IOutbox
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.outbox_records import (
    DeliveryTarget,
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
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity

logger = logging.getLogger("App.Alerting")

#: How often finished alerts older than the retention are deleted.
PURGE_EVERY = timedelta(hours=1)


class AlertHub(IAlertPublisher, IDeliveryFollowUp):
    def __init__(
        self,
        outbox: IOutbox,
        catalog: IAlertChannelCatalog,
        settings: IAlertSettingsSource,
        clock: IAlertClock,
        wakeup: IDeliveryWakeup,
        noise: NoisePolicy,
        delivery: DeliveryPolicy,
    ) -> None:
        self._outbox = outbox
        self._catalog = catalog
        self._settings = settings
        self._clock = clock
        self._wakeup = wakeup
        self._delivery = delivery
        self._lock = threading.RLock()
        self._router = AlertRouter()
        self._dedup = AlertDeduplicator(noise)
        self._coalescer = AlertCoalescer(noise)
        self._book = ConditionBook(noise)
        self._hold = QuietHoursHold()
        self._admission = DeliveryAdmission(outbox, delivery)
        self._next_purge: datetime | None = None

    # -- IAlertPublisher ------------------------------------------------------

    def publish(self, alert: Alert) -> None:
        with self._lock:
            self._accept(alert, self._clock.now(), frozenset())

    def condition_cleared(self, dedup_key: str, at: datetime) -> None:
        with self._lock:
            if self._coalescer.discard(dedup_key):
                return  # never sent, so nothing to recover from
            original = self._book.close(dedup_key)
            if original is None:
                return
            self._accept(
                Alert(
                    original.kind,
                    Severity.INFO,
                    original.subject,
                    f"Recovered: {original.title}",
                    "The condition has cleared.",
                    at,
                    f"{dedup_key}:recovered",
                    recovery=True,
                ),
                self._clock.now(),
                frozenset(),
            )

    # -- the scheduler's tick -------------------------------------------------

    def flush_due(self) -> None:
        """Send what has waited long enough: grouped alerts whose window ended and
        the quiet-hours summary once the period is over. Driven by the scheduler."""
        with self._lock:
            now = self._clock.now()
            for group in self._coalescer.take_due(now):
                alert_id = self._dispatch(group.alert, now, frozenset())
                self._dedup.attach(group.member_keys, alert_id)
            summary = self._hold.release(self._settings.current(), now)
            if summary is not None:
                self._dispatch(summary, now, frozenset())
            self._purge_when_due(now)

    def suppressed_count(self, inhibitor_key: str) -> int:
        """How many alerts the live condition `inhibitor_key` has hidden."""
        with self._lock:
            return self._book.suppressed_count(inhibitor_key)

    # -- IDeliveryFollowUp ----------------------------------------------------

    def channel_failing(self, channel_id: str, reason: str) -> None:
        with self._lock:
            now = self._clock.now()
            self._accept(
                Alert.raised(
                    AlertKind.CHANNEL_FAILING,
                    AlertSubject.app(),
                    f"Alert channel failing: {channel_id}",
                    f"{channel_id}: {reason}",
                    now,
                    channel_id,
                ),
                now,
                frozenset({channel_id}),
            )

    def fail_over(self, alert_id: int, failed_channel_id: str) -> bool:
        with self._lock:
            held = self._outbox.channels_of(alert_id)
            disabled = self._settings.current().disabled_channels
            for channel_id in self._catalog.channel_ids():
                if channel_id in held or channel_id in disabled:
                    continue
                self._outbox.add_delivery(
                    alert_id,
                    DeliveryTarget(channel_id, Loudness.LOUD),
                    self._clock.now(),
                )
                logger.info(
                    "[alert-failover] alert %s: %s asked to wait, queued on %s",
                    alert_id,
                    failed_channel_id,
                    channel_id,
                )
                self._wakeup.notify()
                return True
        logger.warning(
            "[alert-failover] alert %s: %s asked to wait and no other channel is left",
            alert_id,
            failed_channel_id,
        )
        return False

    # -- the path of one alert ------------------------------------------------

    def _accept(self, alert: Alert, now: datetime, excluded: frozenset[str]) -> None:
        inhibitor = self._book.inhibitor_of(alert, now)
        if inhibitor is not None:
            self._book.count_suppressed(inhibitor.dedup_key)
            logger.debug(
                "[alert-inhibited] %s hidden by %s",
                alert.dedup_key,
                inhibitor.dedup_key,
            )
            return
        repeat = self._dedup.repeat_of(alert, now)
        if repeat is not None:
            if repeat.alert_id is not None:
                self._outbox.bump(repeat.alert_id, now)
            return
        if self._hold.holds(alert, self._settings.current(), now):
            self._hold.hold(alert)
            self._dedup.remember(alert, now, self._outbox.enqueue(alert, (), now))
            return
        if self._coalescer.wants(alert):
            self._dedup.remember(alert, now, None)
            self._coalescer.add(alert, now)
            return
        self._dispatch(alert, now, excluded)

    def _dispatch(self, alert: Alert, now: datetime, excluded: frozenset[str]) -> int:
        targets = self._router.route(
            alert, self._settings.current(), self._catalog.channel_ids(), excluded
        )
        admitted = self._admission.admit(targets, alert.severity)
        alert_id = self._outbox.enqueue(alert, admitted, now)
        self._dedup.remember(alert, now, alert_id)
        self._book.open(alert, now)
        if any(target.state is DeliveryState.PENDING for target in admitted):
            self._wakeup.notify()
        logger.debug(
            "[alert-routed] %s -> %s",
            alert.dedup_key,
            [target.channel_id for target in admitted] or "no channel",
        )
        return alert_id

    def _purge_when_due(self, now: datetime) -> None:
        if self._next_purge is not None and now < self._next_purge:
            return
        self._next_purge = now + PURGE_EVERY
        removed = self._outbox.purge_finished_before(now - self._delivery.retention)
        if removed:
            logger.info("[alert-outbox] purged %s finished alerts", removed)
