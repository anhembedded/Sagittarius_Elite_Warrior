"""Fail-over, the channel's waits and the failing flag (N8, review round 1)."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.delivery_result import (
    DeliveryResult,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_group import AlertGroup
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_policies import (
    DeliveryPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_route import AlertRoute
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_settings import (
    AlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.delivery_state import (
    DeliveryState,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import (
    FAST,
    an_alert,
    build_rig,
    states_of,
)


def _stop_failed_on(rig, channel_id: str) -> int:  # type: ignore[no-untyped-def]
    """How many STOP_FAILED the channel received (other alerts also reach it)."""
    return rig.received_kinds(channel_id).count(AlertKind.STOP_FAILED)


def _three_channels(tmp_path: Path, policy: DeliveryPolicy | None = None):  # type: ignore[no-untyped-def]
    """phone and backup hear BOT_EVENTS (N8 lifts the second); pager is the spare."""
    rig = build_rig(
        tmp_path, channel_ids=("phone", "backup", "pager"), delivery_policy=policy
    )
    rig.settings.replace(
        AlertSettings(
            routes=(AlertRoute(AlertGroup.BOT_EVENTS, "pager", Loudness.OFF),)
        )
    )
    return rig


def test_critical_fails_over_when_its_channel_runs_out_of_attempts(
    tmp_path: Path,
) -> None:
    rig = _three_channels(tmp_path, FAST)
    rig.channels["phone"].default = DeliveryResult.failed("timeout")
    rig.hub.publish(an_alert(AlertKind.STOP_FAILED))

    for _ in range(FAST.max_attempts + 1):
        rig.deliver_all()
        rig.clock.advance(timedelta(seconds=30))

    assert _stop_failed_on(rig, "pager") == 1
    [sent] = [
        r
        for r in rig.channels["pager"].received
        if r.alert.kind is AlertKind.STOP_FAILED
    ]
    assert sent.loudness is Loudness.LOUD


def test_critical_fails_over_when_its_channel_refuses_it(tmp_path: Path) -> None:
    rig = _three_channels(tmp_path)
    rig.channels["phone"].default = DeliveryResult.refused("webhook deleted")
    rig.hub.publish(an_alert(AlertKind.STOP_FAILED))

    rig.deliver_all()

    assert _stop_failed_on(rig, "pager") == 1


def test_critical_fails_over_when_another_messages_wait_holds_its_channel(
    tmp_path: Path,
) -> None:
    """A 429 answers for the channel: a CRITICAL queued behind it never gets its
    own try, so the wait itself is what must trigger the fail-over."""
    rig = _three_channels(tmp_path)
    rig.channels["phone"].script = [
        DeliveryResult.retry_later(timedelta(hours=1), "rate limited")
    ]
    rig.hub.publish(an_alert(AlertKind.RATE_LIMITED))
    rig.deliver_all()
    assert _stop_failed_on(rig, "pager") == 0

    rig.hub.publish(an_alert(AlertKind.STOP_FAILED))
    rig.deliver_all()

    assert _stop_failed_on(rig, "pager") == 1
    rig.deliver_all()
    assert _stop_failed_on(rig, "pager") == 1  # once


def test_a_short_wait_by_another_message_does_not_fail_a_critical_over(
    tmp_path: Path,
) -> None:
    rig = _three_channels(tmp_path)
    rig.channels["phone"].script = [
        DeliveryResult.retry_later(timedelta(minutes=2), "rate limited")
    ]
    rig.hub.publish(an_alert(AlertKind.RATE_LIMITED))
    rig.deliver_all()

    rig.hub.publish(an_alert(AlertKind.STOP_FAILED))
    rig.deliver_all()

    assert _stop_failed_on(rig, "pager") == 0


def _failover_boundary(tmp_path: Path, wait: timedelta) -> int:
    rig = _three_channels(tmp_path)
    rig.channels["phone"].script = [DeliveryResult.retry_later(wait, "rate limited")]
    rig.hub.publish(an_alert(AlertKind.STOP_FAILED))
    rig.deliver_all()
    return _stop_failed_on(rig, "pager")


def test_the_five_minute_failover_boundary_is_exclusive(tmp_path: Path) -> None:
    five = timedelta(minutes=5)

    assert _failover_boundary(tmp_path / "at", five) == 0
    assert _failover_boundary(tmp_path / "over", five + timedelta(seconds=1)) == 1


def test_a_second_channel_failing_after_the_first_recovered_raises_its_own_notice(
    tmp_path: Path,
) -> None:
    """The failing flag holds past the hub's dedup window and clears when the
    channel delivers again."""
    rig = build_rig(tmp_path, delivery_policy=FAST)
    phone = rig.channels["phone"]
    phone.default = DeliveryResult.failed("down")

    def exhaust(reason: str) -> None:
        rig.hub.publish(an_alert(AlertKind.BOT_HALTED, reason=reason))
        for _ in range(FAST.max_attempts + 1):
            rig.deliver_all()
            rig.clock.advance(timedelta(seconds=30))

    def notices() -> int:
        return rig.received_kinds("backup").count(AlertKind.CHANNEL_FAILING)

    exhaust("one")
    assert notices() == 1
    rig.clock.advance(timedelta(minutes=20))  # past the 15-minute dedup window
    exhaust("two")
    assert notices() == 1  # still the same failure

    phone.default = DeliveryResult.sent()
    rig.clock.advance(timedelta(minutes=20))
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED, reason="three"))
    rig.deliver_all()  # delivers again: the channel is well
    phone.default = DeliveryResult.failed("down again")
    rig.clock.advance(timedelta(minutes=20))
    exhaust("four")
    assert notices() == 2


def test_rate_limit_answers_do_not_count_toward_the_attempts(tmp_path: Path) -> None:
    rig = build_rig(tmp_path, channel_ids=("phone",), delivery_policy=FAST)
    phone = rig.channels["phone"]
    wait = timedelta(seconds=2)
    phone.script = [DeliveryResult.retry_later(wait, "rate limited")] * 6
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))

    for _ in range(8):
        rig.deliver_all()
        rig.clock.advance(wait)

    assert states_of(rig, "phone") == [DeliveryState.SENT]
    assert len(phone.received) == 7
    [entry] = rig.outbox.history(10)
    assert entry.deliveries[0].attempts == 1  # the six waits used none


def test_endless_rate_limiting_ends_at_the_expiry_not_at_a_failure(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path, channel_ids=("phone",), delivery_policy=FAST)
    rig.channels["phone"].default = DeliveryResult.retry_later(
        timedelta(hours=1), "rate limited"
    )
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))

    for _ in range(26):
        rig.deliver_all()
        rig.clock.advance(timedelta(hours=1))

    assert states_of(rig, "phone") == [DeliveryState.EXPIRED]
    assert (
        rig.received_kinds("backup" if "backup" in rig.channels else "phone").count(
            AlertKind.CHANNEL_FAILING
        )
        == 0
    )


def test_a_wait_the_channel_asked_for_survives_a_restart(tmp_path: Path) -> None:
    first = build_rig(tmp_path, channel_ids=("phone",))
    first.channels["phone"].script = [
        DeliveryResult.retry_later(timedelta(minutes=10), "rate limited")
    ]
    first.hub.publish(an_alert(AlertKind.BOT_HALTED, reason="a"))
    first.deliver_all()
    first.outbox.close()

    second = build_rig(tmp_path, channel_ids=("phone",), clock=first.clock)
    second.hub.publish(an_alert(AlertKind.BOT_ERROR, reason="b"))
    second.clock.advance(timedelta(seconds=1))
    second.deliver_all()
    assert second.channels["phone"].received == []  # still inside the 10 minutes

    second.clock.advance(timedelta(minutes=10))
    second.deliver_all()
    assert len(second.channels["phone"].received) == 2


def _held_critical_failover(tmp_path: Path, wait: timedelta) -> int:
    rig = _three_channels(tmp_path)
    rig.channels["phone"].script = [DeliveryResult.retry_later(wait, "rate limited")]
    rig.hub.publish(an_alert(AlertKind.RATE_LIMITED))
    rig.deliver_all()
    rig.hub.publish(an_alert(AlertKind.STOP_FAILED))
    rig.clock.advance(timedelta(seconds=1))
    rig.deliver_all()
    return _stop_failed_on(rig, "pager")


def test_a_critical_held_behind_a_wait_fails_over_only_past_five_minutes(
    tmp_path: Path,
) -> None:
    """The wait is measured from the moment the CRITICAL is looked at, one second
    after the 429, so a 5 min 1 s wait has exactly 5 min left."""
    five = timedelta(minutes=5)

    assert _held_critical_failover(tmp_path / "at", five + timedelta(seconds=1)) == 0
    assert _held_critical_failover(tmp_path / "over", five + timedelta(seconds=2)) == 1
