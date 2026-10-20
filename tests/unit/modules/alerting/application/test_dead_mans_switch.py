"""`EPIC-036E1` (N7) — the dead man's switch pings while the worker is alive, is off
until a check-in URL is stored, and never names that URL."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime, timedelta

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue
from Sagittarius_Elite_Warrior.src.modules.alerting.application.dead_mans_switch import (
    DEAD_MANS_SWITCH_ID,
    DEAD_MANS_SWITCH_SECRET,
    FAILURES_BEFORE_ALERT,
    PING_EVERY,
    RETRY_AFTER_FAILURE,
    DeadMansSwitch,
    is_check_in_url,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_delivery_follow_up import (
    IDeliveryFollowUp,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_webhook_transport import (
    IWebhookTransport,
    WebhookResponse,
    WebhookUnreachableError,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_worker_liveness import (
    IWorkerLiveness,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_clock import (
    FakeAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_webhook_transport import (
    FakeWebhookTransport,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import InMemorySecretStore

URL = "https://hc-ping.com/9f1c0d2e-7b3a-4c55-8e21-0a6d3b5c7f10"
CHECK_ID = "9f1c0d2e-7b3a-4c55-8e21-0a6d3b5c7f10"
SECOND = timedelta(seconds=1)


class _Liveness(IWorkerLiveness):
    def __init__(self) -> None:
        self.alive = True

    def is_alive(self) -> bool:
        return self.alive

    def stalled(self) -> tuple[str, ...]:
        return () if self.alive else ("alerting-lane-discord",)


class _FollowUp(IDeliveryFollowUp):
    def __init__(self) -> None:
        self.failing: list[tuple[str, str]] = []

    def channel_failing(self, channel_id: str, reason: str) -> None:
        self.failing.append((channel_id, reason))

    def fail_over(self, alert_id: int, failed_channel_id: str) -> bool:
        raise AssertionError("the switch never fails an alert over")


class _World:
    def __init__(self, url: str | None = URL) -> None:
        self.clock = FakeAlertClock()
        self.transport = FakeWebhookTransport()
        self.liveness = _Liveness()
        self.follow_up = _FollowUp()
        self.secrets = InMemorySecretStore(
            **({DEAD_MANS_SWITCH_SECRET: url} if url is not None else {})
        )
        self.switch = DeadMansSwitch(
            self.secrets, self.transport, self.clock, self.liveness, self.follow_up
        )

    def pings(self) -> int:
        return len(self.transport.posts)


def test_the_dead_mans_switch_is_off_by_default() -> None:
    world = _World(url=None)

    world.switch.tick()
    world.clock.advance(PING_EVERY * 3)
    world.switch.tick()

    assert world.pings() == 0


@pytest.mark.parametrize(
    "stored", ["not a url", "http://hc-ping.com/abc", "https://", "ftp://x/y"]
)
def test_a_stored_value_that_is_not_an_https_url_pings_nothing(stored: str) -> None:
    world = _World(url=stored)

    world.switch.tick()

    assert world.pings() == 0


def test_a_valid_url_is_pinged_at_once_and_to_that_url() -> None:
    world = _World()

    world.switch.tick()

    assert [post.url for post in world.transport.posts] == [URL]


def test_the_ping_is_sent_every_five_minutes_while_the_worker_is_alive() -> None:
    world = _World()
    world.switch.tick()

    world.clock.advance(PING_EVERY - SECOND)
    world.switch.tick()
    assert world.pings() == 1  # one second early: nothing

    world.clock.advance(SECOND)
    world.switch.tick()
    assert world.pings() == 2  # at the boundary: a ping

    world.clock.advance(PING_EVERY)
    world.switch.tick()
    assert world.pings() == 3


def test_a_wedged_worker_stops_the_ping_and_a_recovered_one_resumes_it() -> None:
    world = _World()
    world.switch.tick()
    world.liveness.alive = False

    for _ in range(4):
        world.clock.advance(PING_EVERY)
        world.switch.tick()
    assert world.pings() == 1

    world.liveness.alive = True
    world.switch.tick()
    assert world.pings() == 2


def test_a_lost_ping_is_tried_again_after_a_minute_not_after_five() -> None:
    world = _World()
    world.transport.script = [WebhookUnreachableError("timed out")]
    world.switch.tick()

    world.clock.advance(RETRY_AFTER_FAILURE - SECOND)
    world.switch.tick()
    assert world.pings() == 1

    world.clock.advance(SECOND)
    world.switch.tick()
    assert world.pings() == 2
    world.clock.advance(PING_EVERY - SECOND)
    world.switch.tick()
    assert world.pings() == 2  # the success restored the five-minute rhythm


def test_a_monitor_that_stays_down_is_reported_once_as_a_failing_channel() -> None:
    world = _World()
    world.transport.default = WebhookUnreachableError("timed out")

    for _ in range(FAILURES_BEFORE_ALERT - 1):
        world.switch.tick()
        world.clock.advance(RETRY_AFTER_FAILURE)
    assert world.follow_up.failing == []

    world.switch.tick()
    assert [channel for channel, _ in world.follow_up.failing] == [DEAD_MANS_SWITCH_ID]

    for _ in range(3):
        world.clock.advance(RETRY_AFTER_FAILURE)
        world.switch.tick()
    assert len(world.follow_up.failing) == 1


def test_a_success_resets_the_count_of_failures_in_a_row() -> None:
    lost = WebhookUnreachableError("timed out")
    world = _World()
    world.transport.script = [lost, lost, WebhookResponse(200), lost, lost]
    assert (
        FAILURES_BEFORE_ALERT == 3
    )  # two in a row on each side of the success is under it

    for _ in range(5):
        world.switch.tick()
        world.clock.advance(PING_EVERY)

    assert world.follow_up.failing == []


def test_a_refused_ping_counts_as_a_failure() -> None:
    world = _World()
    world.transport.default = WebhookResponse(404)

    for _ in range(FAILURES_BEFORE_ALERT):
        world.switch.tick()
        world.clock.advance(RETRY_AFTER_FAILURE)

    [(_, reason)] = world.follow_up.failing
    assert "refused" in reason
    assert "404" in reason


def test_the_url_is_read_at_each_ping_so_a_rotated_one_is_used() -> None:
    world = _World()
    world.switch.tick()
    other = "https://hc.example.org/ping/other-check"
    world.secrets.write(DEAD_MANS_SWITCH_SECRET, other)

    world.clock.advance(PING_EVERY)
    world.switch.tick()

    assert [post.url for post in world.transport.posts] == [URL, other]


def test_the_ping_url_never_appears_in_a_log_or_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = _World()
    world.transport.default = WebhookUnreachableError("timed out")
    with caplog.at_level(logging.DEBUG, logger="App.Alerting"):
        for _ in range(FAILURES_BEFORE_ALERT + 1):
            world.switch.tick()
            world.clock.advance(RETRY_AFTER_FAILURE)
        world.liveness.alive = False
        world.switch.tick()
        bad = _World(url="http://hc-ping.com/" + CHECK_ID)
        bad.switch.tick()
        world.secrets.write(DEAD_MANS_SWITCH_SECRET, URL)
        world.transport.default = WebhookResponse(204)
        world.liveness.alive = True
        world.switch.tick()

    everything = caplog.text + repr(world.follow_up.failing)
    assert CHECK_ID not in everything
    assert "hc-ping.com" not in everything
    assert "dead-mans-switch" in caplog.text  # the lines exist; they just name no URL


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://hc-ping.com/abc", True),
        ("https://example.org:8443/ping?x=1", True),
        ("http://hc-ping.com/abc", False),
        ("https:///path", False),
        ("", False),
    ],
)
def test_what_counts_as_a_check_in_url(value: str, expected: bool) -> None:
    assert is_check_in_url(value) is expected


@pytest.mark.parametrize(
    ("stored", "level"),
    [(URL, logging.INFO), (None, logging.INFO), ("not a url", logging.WARNING)],
    ids=["on", "off", "invalid"],
)
def test_the_log_lines_name_the_credential_the_switch_reads(
    caplog: pytest.LogCaptureFixture, stored: str | None, level: int
) -> None:
    world = _World(url=stored)
    with caplog.at_level(logging.INFO, logger="App.Alerting"):
        world.switch.tick()

    [record] = [r for r in caplog.records if "[dead-mans-switch]" in r.getMessage()]
    assert DEAD_MANS_SWITCH_SECRET in record.getMessage()
    assert record.levelno == level


class _BreakingTransport(IWebhookTransport):
    """A transport that breaks the port's promise: it raises something that is not
    `WebhookUnreachableError`, with the URL in the message as `http.client.InvalidURL` does."""

    def __init__(self) -> None:
        self.calls = 0

    def post_json(self, url: str, body: Mapping[str, JsonValue]) -> WebhookResponse:
        self.calls += 1
        raise ValueError(f"URL can't contain control characters: {url}")


def test_any_other_transport_error_is_a_failed_ping_and_never_quotes_the_url(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = _World()
    breaking = _BreakingTransport()
    world.switch = DeadMansSwitch(
        world.secrets, breaking, world.clock, world.liveness, world.follow_up
    )

    with caplog.at_level(logging.DEBUG, logger="App.Alerting"):
        for _ in range(FAILURES_BEFORE_ALERT + 2):
            world.switch.tick()  # raises nothing
            world.clock.advance(RETRY_AFTER_FAILURE)

    assert breaking.calls == FAILURES_BEFORE_ALERT + 2  # retried at the 1-minute rhythm
    [(channel, reason)] = world.follow_up.failing
    assert channel == DEAD_MANS_SWITCH_ID
    assert "ValueError" in reason
    assert CHECK_ID not in reason + caplog.text


def test_a_failed_ping_waits_before_the_next_try_whatever_the_error() -> None:
    world = _World()
    breaking = _BreakingTransport()
    world.switch = DeadMansSwitch(
        world.secrets, breaking, world.clock, world.liveness, world.follow_up
    )

    world.switch.tick()
    for _ in range(100):
        world.switch.tick()  # the clock has not moved: no retry storm

    assert breaking.calls == 1


@pytest.mark.parametrize(
    "value",
    [
        "https://hc-ping.com/abc def",
        "https://hc-ping.com/abc\ndef",
        "https://hc-ping.com/\x00",
    ],
    ids=["space", "newline", "nul"],
)
def test_a_url_with_whitespace_or_control_characters_is_not_a_check_in_url(
    value: str,
) -> None:
    assert is_check_in_url(value) is False


class _SettableClock(IAlertClock):
    """A wall clock a test can step back, as a clock jump at boot does."""

    def __init__(self, at: datetime) -> None:
        self.at = at

    def now(self) -> datetime:
        return self.at


def test_a_clock_that_steps_back_does_not_postpone_the_next_ping() -> None:
    world = _World()
    clock = _SettableClock(world.clock.now())
    world.switch = DeadMansSwitch(
        world.secrets, world.transport, clock, world.liveness, world.follow_up
    )
    world.switch.tick()
    assert world.pings() == 1

    clock.at -= timedelta(hours=1)
    world.switch.tick()

    assert world.pings() == 2
