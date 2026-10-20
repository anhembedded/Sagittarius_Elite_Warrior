"""A channel that keeps itself under the platform's rate limit (`EPIC-036C2`).

Wraps any `IAlertChannel`. A send over `PacingPolicy` is not made: the wrapper answers
`DeliveryResult.retry_later(wait)`, the answer a 429 gets, so the worker pauses the channel for
exactly that long and uses no attempt (`ChannelDelivery._attempt`). A burst (the per-fill messages
of `BOT-189`, twenty bots losing a feed) is therefore spread over seconds instead of tripping the
platform's limit, and nothing is lost: the waiting messages stay in the outbox, CRITICAL first.

A try the platform answered with a failure still counts against the window: it reached the
platform. The wrapper passes the platform's own answer through unchanged.

@par Extension cases
  - another platform with a documented limit - a `PacingPolicy` beside `DISCORD_PACING` and one
    line in `composition/channel_bindings.py`;
  - the limit read from the platform's own headers (`X-RateLimit-Remaining`) - a second source of
    the wait, in the channel that sees the headers; this window stays the floor.
"""

from __future__ import annotations

import threading
from collections import deque
from datetime import datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.delivery_result import (
    DeliveryResult,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_channel import (
    IAlertChannel,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_policies import (
    PacingPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness


class SendWindow:
    """The instants of the last sends, forgotten once they are older than the period."""

    def __init__(self, policy: PacingPolicy) -> None:
        self._policy = policy
        self._sent: deque[datetime] = deque()

    def wait_for(self, now: datetime) -> timedelta | None:
        """How long until a send is allowed; `None` when one is allowed now."""
        while self._sent and self._sent[0] <= now - self._policy.per:
            self._sent.popleft()
        if len(self._sent) < self._policy.max_sends:
            return None
        return self._sent[0] + self._policy.per - now

    def record(self, now: datetime) -> None:
        self._sent.append(now)


class PacedChannel(IAlertChannel):
    def __init__(
        self, inner: IAlertChannel, clock: IAlertClock, policy: PacingPolicy
    ) -> None:
        self._inner = inner
        self._clock = clock
        self._policy = policy
        self._window = SendWindow(policy)
        self._lock = threading.Lock()

    def deliver(self, alert: Alert, loudness: Loudness) -> DeliveryResult:
        with self._lock:
            now = self._clock.now()
            wait = self._window.wait_for(now)
            if wait is not None:
                return DeliveryResult.retry_later(
                    wait,
                    f"pacing: at most {self._policy.max_sends} message(s) per "
                    f"{self._policy.per.total_seconds():g} s",
                )
            self._window.record(now)
        return self._inner.deliver(alert, loudness)
