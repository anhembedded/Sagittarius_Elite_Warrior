"""`EPIC-035B` — the supervisor both Binance user-data streams run under.

The stream is the only record of a resting order's fill as it happens
(`BOT-173`), so it must outlive anything the link
or the library throws at it. `python-binance==1.0.37` raises, out of the
socket, `ValueError` (its subscribe step returned no subscription id),
`BinanceWebsocketUnableToConnect` (its own reconnect budget of five is spent),
`ReadLoopClosed`, `BinanceAPIException` from the listen-key or subscribe call,
and whatever the transport raises; the old loop caught two of them and the
rest ended the task for good. This supervisor catches **everything but
cancellation**, backs off exponentially (capped, jittered), publishes the
stream's health, and asks nothing of the library beyond a fresh session per
attempt.

@par The pattern
A supervisor loop with exponential backoff and an explicit health state is the
vetted shape for a long-lived client connection: the retry policy is a value
(`ReconnectPolicy`), the loop is one function, and the health is an event.

@par Extension cases (`architecture-rule.md` §7.2.1)
  · a third stream (margin, a coin-margined venue) is one more `open_session`
    behind this loop, no change here;
  · a different retry policy (a flatter cap on a venue that bans on reconnect
    storms) is one more `ReconnectPolicy` value handed to the stream;
  · a circuit breaker that gives up after N hours is one more rule in `run`,
    and the consumers already learn the outage's age from the events.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.transport_failure_redaction import (
    redact_secrets,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.venue_event_emitter import (
    VenueEventEmitter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.user_stream_health_event import (
    UserStreamState,
)

logger = logging.getLogger("App.UserDataStream")

#: One session: connect, call the given function once subscribed, read until
#: asked to stop. It raises when the connection is lost or cannot be made, and
#: returns when the stream is no longer wanted.
OpenSession = Callable[[Callable[[], None]], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class ReconnectPolicy:
    """How long to wait before the next attempt."""

    #: The first retry waits this long (s).
    base_seconds: float = 1.0
    #: No retry waits longer than this before jitter (s). Binance cuts every
    #: websocket at 24 h, so a reconnect is routine; a minute keeps an outage
    #: short without hammering a host that is down.
    cap_seconds: float = 60.0
    #: The delay is scaled by a factor in [1 - f, 1 + f], so a fleet of
    #: clients dropped together does not return together.
    jitter_fraction: float = 0.2
    #: A connection that lived this long (s) counts as healthy: the next
    #: failure starts the backoff over. A flapping link that connects and
    #: drops at once keeps growing its delay instead.
    stable_after_seconds: float = 30.0

    def delay(self, attempt: int, spread: float) -> float:
        """The wait before retry number `attempt` (0 first); `spread` is a
        draw in [0, 1) that places the jitter."""
        # `min` before the power: attempt can be large after a long outage.
        raw = min(self.cap_seconds, self.base_seconds * 2 ** min(attempt, 62))
        factor = 1 - self.jitter_fraction + 2 * self.jitter_fraction * spread
        return raw * factor


DEFAULT_RECONNECT_POLICY = ReconnectPolicy()


def _utc_now() -> datetime:
    return datetime.now(UTC)


#: Jitter is not security, but `SystemRandom` keeps `S311` honest and shares no
#: state between the two streams' draws.
_JITTER_DRAW = random.SystemRandom().random


class UserStreamSupervisor:
    """Keeps one venue's stream connected, and says whether it is."""

    def __init__(
        self,
        label: str,
        events: VenueEventEmitter,
        policy: ReconnectPolicy = DEFAULT_RECONNECT_POLICY,
        *,
        now: Callable[[], datetime] = _utc_now,
        monotonic: Callable[[], float] = time.monotonic,
        spread: Callable[[], float] = _JITTER_DRAW,
    ) -> None:
        self._label = label
        self._events = events
        self._policy = policy
        self._now = now
        self._monotonic = monotonic
        self._spread = spread

    def publish_stopped(self) -> None:
        self._events.user_stream_health(UserStreamState.STOPPED, self._now())

    async def run(
        self, open_session: OpenSession, is_current: Callable[[], bool]
    ) -> None:
        """Run sessions until `is_current()` is False.

        @details `is_current` is the caller's fence (its cancellation token
        and its generation, `BUG-094`): a superseded or stopped stream ends
        here without another attempt or another event.
        """
        started = self._now()
        outage_since: datetime | None = started
        attempt = 0
        self._events.user_stream_health(UserStreamState.CONNECTING, started)
        while is_current():
            connected_at: float | None = None

            def mark_connected() -> None:
                nonlocal connected_at, outage_since
                connected_at = self._monotonic()
                outage_since = None
                self._events.user_stream_health(UserStreamState.CONNECTED, self._now())

            try:
                await open_session(mark_connected)
            except asyncio.CancelledError:
                logger.info("%s task was cancelled.", self._label)
                break
            except Exception as exc:  # noqa: BLE001 - the supervisor's job: nothing ends the stream but a stop
                failure = f"{type(exc).__name__}: {redact_secrets(str(exc))}"
            else:
                failure = "the session ended without being asked to stop"
            if not is_current():
                break
            if (
                connected_at is not None
                and self._monotonic() - connected_at
                >= self._policy.stable_after_seconds
            ):
                attempt = 0
            if outage_since is None:
                outage_since = self._now()
            attempt += 1
            delay = self._policy.delay(attempt - 1, self._spread())
            logger.error(
                "%s connection lost (attempt %d): %s. Retrying in %.1fs...",
                self._label,
                attempt,
                failure,
                delay,
            )
            self._events.user_stream_health(
                UserStreamState.RECONNECTING, outage_since, attempt
            )
            await asyncio.sleep(delay)
