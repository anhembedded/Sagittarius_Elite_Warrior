"""The dead man's switch: a ping to an external monitor while the app is alive
(`EPIC-036E1`, N7).

An app that dies, or a machine that powers off, cannot report it. This sends one
small POST to a check-in URL every `PING_EVERY`; the monitor (healthchecks.io or
any service that alerts when its URL goes quiet) tells the owner when the pings
stop. Everything the owner needs from it is *silence*, so the switch sends only
while `IWorkerLiveness` says the alert worker is making progress: a wedged worker
stops the ping and the monitor fires.

**Off by default.** With no check-in URL stored, `tick` does nothing. **The URL is
a secret** (whoever holds it can fake a heartbeat): it is read by name from
`ISecretStore` at each ping, never kept, and no log line, reason or exception
names it. **It never touches an alert**: `tick` runs on its own thread
(`ThreadedDeliveryHost`), so a monitor that is slow or down delays no delivery,
and its failure is reported as a failing channel, once.

Not an `IAlertChannel`: it carries no alert, only liveness.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from Sagittarius_Elite_Warrior.src.core.contracts.i_secret_store import ISecretStore
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_delivery_follow_up import (
    IDeliveryFollowUp,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_webhook_transport import (
    IWebhookTransport,
    WebhookUnreachableError,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_worker_liveness import (
    IWorkerLiveness,
)

logger = logging.getLogger("App.Alerting")

#: The secret's name in every store: the systemd credential's name in the unit
#: file, the keyring entry's name on a desktop.
DEAD_MANS_SWITCH_SECRET = "alerting_deadman_ping_url"  # noqa: S105 - the name of a secret, not a secret

#: The id the failure is reported under, as a failing channel (`CHANNEL_FAILING`).
DEAD_MANS_SWITCH_ID = "dead_mans_switch"

#: How often a healthy app pings (N7). The monitor's period is set to match.
PING_EVERY = timedelta(minutes=5)

#: How soon a ping that failed is tried again, so one lost packet is not a missed beat.
RETRY_AFTER_FAILURE = timedelta(minutes=1)

#: Failed pings in a row before the owner is told the switch itself is down.
FAILURES_BEFORE_ALERT = 3


_ON, _OFF, _INVALID = "on", "off", "invalid"


def is_check_in_url(value: str) -> bool:
    """An `https` URL with a host: the only shape a check-in URL has."""
    parts = urlsplit(value)
    return parts.scheme == "https" and bool(parts.hostname)


class DeadMansSwitch:
    def __init__(
        self,
        secrets: ISecretStore,
        transport: IWebhookTransport,
        clock: IAlertClock,
        liveness: IWorkerLiveness,
        follow_up: IDeliveryFollowUp,
    ) -> None:
        self._secrets = secrets
        self._transport = transport
        self._clock = clock
        self._liveness = liveness
        self._follow_up = follow_up
        self._next_at: datetime | None = None
        self._failures = 0
        self._announced: str | None = None
        self._wedged_logged = False

    def tick(self) -> None:
        """Ping if a ping is due and the worker is alive. Called from one thread,
        often; does no I/O until a ping is due."""
        now = self._clock.now()
        if self._next_at is not None and now < self._next_at:
            return
        if not self._liveness.is_alive():
            if not self._wedged_logged:
                self._wedged_logged = True
                logger.warning(
                    "[dead-mans-switch] the alert worker is not making progress "
                    "(stalled: %s); no ping is sent, so the monitor will raise the alarm",
                    ", ".join(self._liveness.stalled()) or "none registered",
                )
            return
        if self._wedged_logged:
            self._wedged_logged = False
            logger.info("[dead-mans-switch] the alert worker is making progress again")
        url = (self._secrets.read(DEAD_MANS_SWITCH_SECRET) or "").strip()
        if not is_check_in_url(url):
            self._announce(_INVALID if url else _OFF)
            self._next_at = now + PING_EVERY
            return
        self._announce(_ON)
        self._ping(url, now)

    def _ping(self, url: str, now: datetime) -> None:
        try:
            response = self._transport.post_json(url, {})
        except WebhookUnreachableError as error:
            self._failed(f"the monitor did not answer ({error})", now)
            return
        if not response.accepted:
            self._failed(f"the monitor refused the ping (HTTP {response.status})", now)
            return
        if self._failures >= FAILURES_BEFORE_ALERT:
            logger.info("[dead-mans-switch] the monitor answers again")
        self._failures = 0
        self._next_at = now + PING_EVERY
        logger.debug("[dead-mans-switch] pinged")

    def _failed(self, reason: str, now: datetime) -> None:
        self._failures += 1
        self._next_at = now + RETRY_AFTER_FAILURE
        logger.warning(
            "[dead-mans-switch] ping failed (%s in a row): %s", self._failures, reason
        )
        if self._failures == FAILURES_BEFORE_ALERT:
            self._follow_up.channel_failing(DEAD_MANS_SWITCH_ID, reason)

    def _announce(self, state: str) -> None:
        """Log the switch's state once per change; never the URL."""
        if state == self._announced:
            return
        self._announced = state
        if state == _ON:
            logger.info(
                "[dead-mans-switch] on: pinging the check-in URL in the credential "
                "%s every %s s",
                DEAD_MANS_SWITCH_SECRET,
                int(PING_EVERY.total_seconds()),
            )
        elif state == _INVALID:
            logger.warning(
                "[dead-mans-switch] off: the credential %s does not hold an https "
                "URL; nothing will tell you if this host goes silent",
                DEAD_MANS_SWITCH_SECRET,
            )
        else:
            logger.info(
                "[dead-mans-switch] off: no check-in URL is stored in the credential %s",
                DEAD_MANS_SWITCH_SECRET,
            )
