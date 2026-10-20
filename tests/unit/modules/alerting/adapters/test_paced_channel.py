"""`EPIC-036C2` - a channel keeps itself under the platform's rate limit instead of finding the
limit by being answered 429: a burst of messages is spread, none is lost, none is retried early."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.paced_channel import (
    PacedChannel,
    SendWindow,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.delivery_result import (
    DeliveryResult,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_channel import (
    FakeAlertChannel,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_clock import (
    FakeAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_policies import (
    PacingPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.delivery_state import (
    DeliveryState,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import (
    an_alert,
    build_rig,
    states_of,
)

POLICY = PacingPolicy(max_sends=4, per=timedelta(seconds=2))


def _paced(
    inner: FakeAlertChannel, clock: FakeAlertClock, policy: PacingPolicy = POLICY
) -> PacedChannel:
    return PacedChannel(inner, clock, policy)


def test_the_window_admits_its_limit_and_names_the_wait_for_the_next() -> None:
    window = SendWindow(POLICY)
    start = FakeAlertClock().now()
    for step in range(4):
        assert window.wait_for(start + timedelta(milliseconds=100 * step)) is None
        window.record(start + timedelta(milliseconds=100 * step))

    wait = window.wait_for(start + timedelta(milliseconds=400))

    # the first send leaves the window two seconds after it was made
    assert wait == timedelta(milliseconds=1600)


def test_the_window_forgets_a_send_once_the_period_has_passed() -> None:
    window = SendWindow(POLICY)
    start = FakeAlertClock().now()
    for _ in range(4):
        window.record(start)

    assert window.wait_for(start + timedelta(seconds=2)) is None


def test_a_send_over_the_limit_is_asked_to_wait_and_the_platform_is_not_called() -> (
    None
):
    clock = FakeAlertClock()
    inner = FakeAlertChannel()
    channel = _paced(inner, clock)
    for _ in range(4):
        assert channel.deliver(an_alert(), Loudness.LOUD).ok

    result = channel.deliver(an_alert(), Loudness.LOUD)

    assert not result.ok
    assert not result.permanent
    assert result.retry_after == timedelta(seconds=2)
    assert "pacing" in result.reason
    assert len(inner.received) == 4


def test_once_the_wait_has_passed_the_next_send_goes_out() -> None:
    clock = FakeAlertClock()
    inner = FakeAlertChannel()
    channel = _paced(inner, clock)
    for _ in range(4):
        channel.deliver(an_alert(), Loudness.LOUD)
    waited = channel.deliver(an_alert(), Loudness.LOUD).retry_after
    assert waited is not None

    clock.advance(waited)

    assert channel.deliver(an_alert(), Loudness.LOUD).ok
    assert len(inner.received) == 5


def test_a_try_the_platform_answered_with_a_failure_still_counts_against_the_limit() -> (
    None
):
    clock = FakeAlertClock()
    inner = FakeAlertChannel(default=DeliveryResult.failed("Discord answered 502"))
    channel = _paced(inner, clock)

    results = [channel.deliver(an_alert(), Loudness.LOUD) for _ in range(5)]

    assert [r.reason for r in results[:4]] == ["Discord answered 502"] * 4
    assert results[4].retry_after is not None
    assert len(inner.received) == 4


def test_the_answer_of_the_platform_is_passed_on_unchanged() -> None:
    clock = FakeAlertClock()
    refused = DeliveryResult.refused("Discord refused the webhook message (404)")
    channel = _paced(FakeAlertChannel(default=refused), clock)

    assert channel.deliver(an_alert(), Loudness.LOUD) == refused


class _TimedChannel(FakeAlertChannel):
    """Remembers the instant of each delivery, by the injected clock."""

    def __init__(self, clock: FakeAlertClock) -> None:
        super().__init__()
        self.at: list[datetime] = []
        self._clock = clock

    def deliver(self, alert: Alert, loudness: Loudness) -> DeliveryResult:
        self.at.append(self._clock.now())
        return super().deliver(alert, loudness)


def test_a_burst_of_fill_messages_is_spread_under_the_limit_and_none_is_lost(
    tmp_path: Path,
) -> None:
    """The real hub, outbox and worker pass over a paced channel (a kind the fill backlog does not bound): thirty messages published at
    one instant reach the channel all, never more than four in any two seconds, with no attempt
    used (a pacing wait is not a failure)."""
    clock = FakeAlertClock()
    timed = _TimedChannel(clock)
    rig = build_rig(tmp_path, clock=clock, channel_map={"phone": _paced(timed, clock)})
    for number in range(30):
        rig.hub.publish(
            an_alert(AlertKind.RATE_LIMITED, at=clock.now(), reason=str(number))
        )

    for _ in range(400):
        rig.delivery.run_due("phone")
        if len(timed.at) == 30:
            break
        clock.advance(timedelta(milliseconds=100))

    assert len(timed.at) == 30
    assert all(
        sum(1 for other in timed.at if at <= other < at + POLICY.per)
        <= POLICY.max_sends
        for at in timed.at
    )
    assert set(states_of(rig, "phone")) == {DeliveryState.SENT}
    # one real try each: a pacing wait uses no attempt
    assert {d.attempts for e in rig.outbox.history(100) for d in e.deliveries} == {1}
