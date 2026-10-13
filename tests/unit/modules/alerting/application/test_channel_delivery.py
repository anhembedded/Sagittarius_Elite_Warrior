"""The worker pass: priority, retry_after, failure containment, failover (N2, N8)."""

from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.sqlite_outbox import (
    SqliteOutbox,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.delivery_result import (
    DeliveryResult,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.outbox_records import (
    DeliveryUpdate,
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
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.delivery_state import (
    DeliveryState,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import (
    FAST,
    an_alert,
    bot_subject,
    build_rig,
    states_of,
)


def test_critical_is_delivered_before_info(tmp_path: Path) -> None:
    rig = build_rig(tmp_path, channel_ids=("phone",))

    rig.hub.publish(an_alert(AlertKind.HEARTBEAT, AlertSubject.app()))
    rig.hub.publish(an_alert(AlertKind.RATE_LIMITED))
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
    rig.deliver_all()

    assert rig.received_kinds("phone") == [
        AlertKind.BOT_HALTED,
        AlertKind.RATE_LIMITED,
        AlertKind.HEARTBEAT,
    ]


def test_info_is_dropped_before_critical_when_the_queue_is_full(tmp_path: Path) -> None:
    rig = build_rig(
        tmp_path, channel_ids=("phone",), delivery_policy=DeliveryPolicy(capacity=3)
    )
    for reason in ("one", "two"):
        rig.hub.publish(
            an_alert(AlertKind.HEARTBEAT, AlertSubject.app(), reason=reason)
        )
    rig.hub.publish(an_alert(AlertKind.RATE_LIMITED))

    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
    rig.deliver_all()

    kinds = rig.received_kinds("phone")
    assert kinds[0] is AlertKind.BOT_HALTED
    assert AlertKind.RATE_LIMITED in kinds
    assert kinds.count(AlertKind.HEARTBEAT) == 1
    assert states_of(rig, "phone").count(DeliveryState.DROPPED) == 1


def test_a_new_info_is_itself_dropped_when_nothing_lower_is_queued(
    tmp_path: Path,
) -> None:
    rig = build_rig(
        tmp_path, channel_ids=("phone",), delivery_policy=DeliveryPolicy(capacity=2)
    )
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
    rig.hub.publish(an_alert(AlertKind.BOT_ERROR))

    rig.hub.publish(an_alert(AlertKind.HEARTBEAT, AlertSubject.app()))
    rig.deliver_all()

    assert rig.received_kinds("phone") == [AlertKind.BOT_HALTED, AlertKind.BOT_ERROR]
    assert DeliveryState.DROPPED in states_of(rig, "phone")


def test_critical_is_never_dropped_even_over_capacity(tmp_path: Path) -> None:
    rig = build_rig(
        tmp_path, channel_ids=("phone",), delivery_policy=DeliveryPolicy(capacity=1)
    )

    for reason in ("a", "b", "c"):
        rig.hub.publish(an_alert(AlertKind.BOT_HALTED, reason=reason))
    rig.deliver_all()

    assert len(rig.channels["phone"].received) == 3
    assert DeliveryState.DROPPED not in states_of(rig, "phone")


def test_retry_after_is_never_retried_early(tmp_path: Path) -> None:
    rig = build_rig(tmp_path, channel_ids=("phone",))
    phone = rig.channels["phone"]
    phone.script = [DeliveryResult.retry_later(timedelta(seconds=60), "rate limited")]
    rig.hub.publish(an_alert())

    rig.deliver_all()
    assert len(phone.received) == 1
    rig.clock.advance(timedelta(seconds=59))
    rig.deliver_all()
    assert len(phone.received) == 1

    rig.clock.advance(timedelta(seconds=1))
    rig.deliver_all()
    assert len(phone.received) == 2
    assert states_of(rig, "phone") == [DeliveryState.SENT]


def test_a_rate_limited_channel_pauses_its_whole_queue(tmp_path: Path) -> None:
    """A 429 answers for the channel, not for one message."""
    rig = build_rig(tmp_path, channel_ids=("phone",))
    phone = rig.channels["phone"]
    phone.script = [DeliveryResult.retry_later(timedelta(seconds=60), "rate limited")]
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
    rig.hub.publish(an_alert(AlertKind.BOT_ERROR))

    rig.deliver_all()
    rig.clock.advance(timedelta(seconds=10))
    rig.deliver_all()  # BOT_ERROR is due, but the channel asked for 60 s

    assert len(phone.received) == 1
    rig.clock.advance(timedelta(seconds=50))
    rig.deliver_all()
    assert len(phone.received) == 3  # the retry, then the one that waited


def test_a_channel_failing_after_its_attempts_raises_channel_failing_once(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path, delivery_policy=FAST)
    rig.channels["phone"].default = DeliveryResult.failed("connection refused")
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
    rig.hub.publish(an_alert(AlertKind.BOT_ERROR))

    for _ in range(6):
        rig.deliver_all()
        rig.clock.advance(timedelta(seconds=30))

    phone_kinds = rig.received_kinds("phone")
    assert phone_kinds.count(AlertKind.BOT_HALTED) == FAST.max_attempts
    assert AlertKind.CHANNEL_FAILING not in phone_kinds
    assert rig.received_kinds("backup").count(AlertKind.CHANNEL_FAILING) == 1
    assert DeliveryState.FAILED in states_of(rig, "phone")


def test_a_refusal_fails_the_delivery_at_once_and_flags_the_channel(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path, delivery_policy=FAST)
    rig.channels["phone"].default = DeliveryResult.refused("webhook deleted")
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))

    rig.deliver_all()

    assert len(rig.channels["phone"].received) == 1
    assert rig.received_kinds("backup").count(AlertKind.CHANNEL_FAILING) == 1


def test_a_channel_that_raises_is_contained(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    rig = build_rig(tmp_path, delivery_policy=FAST)
    rig.channels["phone"].default = RuntimeError("https://hooks.example/SECRET-TOKEN")
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))

    with caplog.at_level(logging.DEBUG, logger="App.Alerting"):
        rig.deliver_all()

    assert len(rig.channels["backup"].received) == 1
    [entry] = rig.outbox.history(10)
    phone = next(d for d in entry.deliveries if d.channel_id == "phone")
    assert phone.state is DeliveryState.RETRYING
    assert phone.attempts == 1
    assert "RuntimeError" in phone.reason
    assert "SECRET-TOKEN" not in phone.reason
    assert "SECRET-TOKEN" not in caplog.text


def test_critical_fails_over_when_retry_after_exceeds_five_minutes(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path, channel_ids=("phone", "backup", "pager"))
    rig.settings.replace(
        AlertSettings(
            routes=(
                AlertRoute(AlertGroup.BOT_EVENTS, "backup", Loudness.OFF),
                AlertRoute(AlertGroup.BOT_EVENTS, "pager", Loudness.OFF),
            )
        )
    )
    rig.channels["phone"].script = [
        DeliveryResult.retry_later(timedelta(minutes=10), "rate limited")
    ]
    rig.channels["backup"].script = [
        DeliveryResult.retry_later(timedelta(minutes=10), "rate limited")
    ]
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))

    rig.deliver_all()  # phone answers first; the pager is reached in the same pass

    assert len(rig.channels["pager"].received) == 1
    assert rig.channels["pager"].received[0].loudness is Loudness.LOUD


def test_critical_does_not_fail_over_for_a_short_retry_after(tmp_path: Path) -> None:
    rig = build_rig(tmp_path, channel_ids=("phone", "backup", "pager"))
    rig.settings.replace(
        AlertSettings(
            routes=(
                AlertRoute(AlertGroup.BOT_EVENTS, "backup", Loudness.OFF),
                AlertRoute(AlertGroup.BOT_EVENTS, "pager", Loudness.OFF),
            )
        )
    )
    rig.channels["phone"].script = [
        DeliveryResult.retry_later(timedelta(minutes=2), "rate limited")
    ]
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))

    rig.deliver_all()
    rig.deliver_all()

    assert rig.channels["pager"].received == []


def test_a_warning_never_fails_over(tmp_path: Path) -> None:
    rig = build_rig(tmp_path, channel_ids=("phone", "backup"))
    rig.settings.replace(
        AlertSettings(routes=(AlertRoute(AlertGroup.NOTICES, "backup", Loudness.OFF),))
    )
    rig.channels["phone"].script = [
        DeliveryResult.retry_later(timedelta(hours=1), "rate limited")
    ]
    rig.hub.publish(an_alert(AlertKind.RATE_LIMITED))

    rig.deliver_all()
    rig.deliver_all()

    assert rig.channels["backup"].received == []


def test_an_alert_older_than_24_hours_expires_and_is_not_sent(tmp_path: Path) -> None:
    rig = build_rig(tmp_path)
    rig.hub.publish(an_alert())

    rig.clock.advance(timedelta(hours=24, seconds=1))
    rig.deliver_all()

    assert [c.received for c in rig.channels.values()] == [[], []]
    assert set(states_of(rig, "phone") + states_of(rig, "backup")) == {
        DeliveryState.EXPIRED
    }


def test_an_alert_exactly_24_hours_old_is_still_sent(tmp_path: Path) -> None:
    rig = build_rig(tmp_path)
    rig.hub.publish(an_alert())

    rig.clock.advance(timedelta(hours=24))
    rig.deliver_all()

    assert [len(c.received) for c in rig.channels.values()] == [1, 1]


class _DiesBeforeRecording(SqliteOutbox):
    """The worker process dying after the channel accepted a message."""

    def mark(self, delivery_id: int, update: DeliveryUpdate) -> None:
        raise KeyboardInterrupt("process died")


def test_a_delivery_is_repeated_if_the_worker_dies_before_it_is_recorded(
    tmp_path: Path,
) -> None:
    """At-least-once: the outbox forgets nothing it was not told was done."""
    path = tmp_path / "state" / "alerts.sqlite3"
    first = build_rig(
        tmp_path, channel_ids=("phone",), outbox=_DiesBeforeRecording(path)
    )
    first.hub.publish(an_alert())
    with pytest.raises(KeyboardInterrupt):
        first.deliver_all()
    first.outbox.close()
    assert len(first.channels["phone"].received) == 1

    second = build_rig(tmp_path, channel_ids=("phone",), clock=first.clock)
    second.deliver_all()
    second.deliver_all()

    assert len(second.channels["phone"].received) == 1  # the repeat, once
    assert states_of(second, "phone") == [DeliveryState.SENT]


def test_the_outbox_survives_a_restart(tmp_path: Path) -> None:
    first = build_rig(tmp_path)
    alert = an_alert(
        AlertKind.STOP_FAILED, bot_subject("durable"), reason="exchange down"
    )
    first.hub.publish(alert)
    first.outbox.close()

    second = build_rig(tmp_path, clock=first.clock)
    second.deliver_all()

    for channel in second.channels.values():
        [item] = channel.received
        assert item.alert == alert
    [entry] = second.outbox.history(10)
    assert entry.record.alert == alert
    assert {d.state for d in entry.deliveries} == {DeliveryState.SENT}


def test_a_second_pass_sends_nothing_twice(tmp_path: Path) -> None:
    rig = build_rig(tmp_path)
    rig.hub.publish(an_alert())

    rig.deliver_all()
    rig.deliver_all()
    rig.clock.advance(timedelta(hours=1))
    rig.deliver_all()

    assert [len(c.received) for c in rig.channels.values()] == [1, 1]
