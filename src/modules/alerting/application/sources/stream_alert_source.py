"""The user-data stream's outage becomes one venue alert (`EPIC-036B1`; widened by `EPIC-036B`).

An anti-corruption layer like `BotAlertSource`: it reads `trading/contracts`' `UserStreamHealthEvent`
and speaks the alerting vocabulary. While the stream is not connected the app is blind about its
resting orders' fills, and the bots halt after `UserStreamLimits.down_limit` (`UserStreamWatch`); this source is the
notice before that, and the one message for a venue whose bots all halt for the same cause.

**Raise.** A `CONNECTING`/`RECONNECTING` event whose outage (`since`) is older than
`EarlyWarningPolicy.stream_down_grace` raises `USER_STREAM_DOWN` for the venue. The supervisor
publishes one event per failed attempt, at most about a minute apart (`ReconnectPolicy.cap_seconds`),
so no timer is needed: an outage that outlasts the grace is told at the next attempt. The routine
24 h reconnect lasts seconds and stays silent.

**Clear.** `CONNECTED` ends the condition (the hub sends "Recovered"). `STOPPED` is a stream
nobody wants any more (trading switched off), not an outage, so it neither raises nor clears.

**Not repeated.** One open warning per venue and a cool-down between two raises
(`WarningLatch`, `EarlyWarningPolicy.stream_cooldown`), so a link that connects and drops again
sends one pair per cool-down and not one per flap. The text names the venue and the duration only;
the stream's failure text is not copied, so nothing from a request can reach an alert.

@par Extension cases
  · a market-data stream (`PRICE_FEED_STALE`, `EPIC-036B`) — a sibling handler in this file's
    style; the hub already lets `USER_STREAM_DOWN` hide a venue's `PRICE_FEED_STALE`.
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.modules.alerting.application.warning_latch import (
    WarningLatch,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_publisher import (
    IAlertPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_catalog import (
    label_of,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_policies import (
    DEFAULT_EARLY_WARNINGS,
    EarlyWarningPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.user_stream_health_event import (
    UserStreamHealthEvent,
    UserStreamState,
)

logger = logging.getLogger("App.Alerting")


class StreamAlertSource:
    def __init__(
        self,
        publisher: IAlertPublisher,
        clock: IAlertClock,
        policy: EarlyWarningPolicy = DEFAULT_EARLY_WARNINGS,
    ) -> None:
        self._publisher = publisher
        self._clock = clock
        self._grace = policy.stream_down_grace
        self._lock = threading.Lock()
        self._outages = WarningLatch(policy.stream_cooldown)

    def on_user_stream_health(self, event: UserStreamHealthEvent) -> None:
        """Runs on the stream's thread; only records, as `IAlertPublisher.publish` does."""
        venue = event.venue.value
        subject = AlertSubject.venue_wide(venue)
        if event.state is UserStreamState.CONNECTED:
            with self._lock:
                now = self._clock.now()
                if self._outages.clear(venue, now):
                    self._publisher.condition_cleared(
                        Alert.condition_key(AlertKind.USER_STREAM_DOWN, subject), now
                    )
            return
        if event.state is UserStreamState.STOPPED:
            return
        now = self._clock.now()
        down_for = now - _aware(event.since)
        if down_for < self._grace:
            return
        detail = (
            f"The {event.venue.display_name} account stream has been down for "
            f"{int(down_for.total_seconds())} s (attempt {event.attempt}). The app cannot see "
            "its resting orders fill meanwhile, and its bots on this venue halt if the stream "
            "stays down much longer. The app keeps reconnecting by itself."
        )
        with self._lock:
            if not self._outages.raise_(venue, now):
                return
            self._publisher.publish(
                Alert.raised(
                    AlertKind.USER_STREAM_DOWN,
                    subject,
                    f"{label_of(AlertKind.USER_STREAM_DOWN)}: {event.venue.display_name}",
                    detail,
                    now,
                )
            )
        logger.info("[alert-source] venue %s: USER_STREAM_DOWN published", venue)


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
