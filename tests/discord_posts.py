"""What a journey counts on a fake Discord transport, without the app's own heartbeat (`BUG-252`).

A booted app starts a housekeeping thread that wakes every second; its first pass sends a heartbeat
because none is stored (`EPIC-036E`, `HeartbeatService`). A journey that runs longer than a second
therefore finds the heartbeat beside the alert it is about, so a count or an unpack of everything
sent depends on how fast the runner is. Every journey over a booted app and a
`FakeWebhookTransport` reads its posts through `posts_without_heartbeat`.

Retire when: the housekeeping thread is injectable in a booted app, so a journey can stand it down
and still boot the real graph.
"""

from __future__ import annotations

import time
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_clock import (
    FakeAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_webhook_transport import (
    FakeWebhookTransport,
    RecordedPost,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_catalog import (
    label_of,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind

#: How much fake time passes per look while waiting: more than a paced channel's whole period.
_STEP_SECONDS = 2
_WAIT_S = 15.0


def is_heartbeat(post: RecordedPost) -> bool:
    """Its title is the alert kind's own label, so a bot's alert cannot match."""
    first_line = str(post.body["content"]).splitlines()[0]
    return f"· {label_of(AlertKind.HEARTBEAT)}" in first_line


def posts_without_heartbeat(transport: FakeWebhookTransport) -> list[RecordedPost]:
    return [post for post in list(transport.posts) if not is_heartbeat(post)]


def wait_until_the_heartbeat_is_told(
    transport: FakeWebhookTransport, clock: IAlertClock
) -> None:
    """Waits, on what was sent and not on a sleep, until the app's own heartbeat has reached the
    channel: what a slow runner does by itself, made certain. `clock` is the fake one the app was
    booted with; it is moved on so a paced channel does not hold the message."""
    assert isinstance(clock, FakeAlertClock), (
        "the journey boots the app with a fake clock"
    )
    deadline = time.monotonic() + _WAIT_S
    while not any(is_heartbeat(post) for post in list(transport.posts)):
        assert time.monotonic() < deadline, "the app never told its heartbeat"
        transport.posted.wait(0.05)
        transport.posted.clear()
        clock.advance(timedelta(seconds=_STEP_SECONDS))
