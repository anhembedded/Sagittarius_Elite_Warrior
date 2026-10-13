"""Recovery: a cleared condition says so once, and a condition that comes back is new."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import (
    SPOT,
    an_alert,
    bot_subject,
    build_rig,
)

FEED = AlertKind.PRICE_FEED_STALE


def test_feed_stale_alerts_flow_again_once_the_venue_recovers(tmp_path: Path) -> None:
    rig = build_rig(tmp_path, channel_ids=("phone",))
    venue_down = an_alert(AlertKind.USER_STREAM_DOWN, AlertSubject.venue_wide(SPOT))
    rig.hub.publish(venue_down)

    rig.hub.condition_cleared(venue_down.dedup_key, rig.clock.now())
    rig.hub.publish(an_alert(FEED, bot_subject("late")))
    rig.clock.advance(timedelta(seconds=11))
    rig.hub.flush_due()
    rig.deliver_all()

    assert rig.received_kinds("phone").count(FEED) == 1


def test_an_inhibitor_that_was_never_cleared_stops_hiding_alerts_after_an_hour(
    tmp_path: Path,
) -> None:
    """A source that forgets to clear must not silence a venue's bots for good."""
    rig = build_rig(tmp_path, channel_ids=("phone",))
    rig.hub.publish(an_alert(AlertKind.USER_STREAM_DOWN, AlertSubject.venue_wide(SPOT)))

    rig.clock.advance(timedelta(hours=1, seconds=1))
    rig.hub.publish(an_alert(FEED, bot_subject("late"), at=rig.clock.now()))
    rig.clock.advance(timedelta(seconds=11))
    rig.hub.flush_due()
    rig.deliver_all()

    assert rig.received_kinds("phone").count(FEED) == 1


def test_a_cleared_condition_sends_one_recovery_alert(tmp_path: Path) -> None:
    rig = build_rig(tmp_path, channel_ids=("phone",))
    halted = an_alert(AlertKind.BOT_HALTED)
    rig.hub.publish(halted)

    rig.clock.advance(timedelta(minutes=5))
    rig.hub.condition_cleared(halted.dedup_key, rig.clock.now())
    rig.hub.condition_cleared(halted.dedup_key, rig.clock.now())
    rig.hub.condition_cleared("never-raised", rig.clock.now())
    rig.deliver_all()

    received = rig.channels["phone"].received
    assert len(received) == 2
    recovery = received[1]
    assert recovery.alert.recovery is True
    assert recovery.alert.kind is AlertKind.BOT_HALTED
    assert recovery.alert.severity is Severity.INFO
    assert recovery.alert.title.startswith("Recovered")
    assert recovery.loudness is Loudness.SILENT


def test_a_condition_cleared_before_its_group_was_sent_sends_nothing(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path, channel_ids=("phone",))
    stale = an_alert(FEED, bot_subject("blip"))
    rig.hub.publish(stale)

    rig.clock.advance(timedelta(seconds=2))
    rig.hub.condition_cleared(stale.dedup_key, rig.clock.now())
    rig.clock.advance(timedelta(seconds=11))
    rig.hub.flush_due()
    rig.deliver_all()

    assert rig.channels["phone"].received == []


def test_a_condition_that_comes_back_after_its_recovery_is_sent_again(
    tmp_path: Path,
) -> None:
    """Raise, clear, raise again inside the dedup window: the second raise is a
    new fact, not a repeat of one the owner was already told was over."""
    rig = build_rig(tmp_path, channel_ids=("phone",))
    halted = an_alert(AlertKind.BOT_HALTED)
    rig.hub.publish(halted)

    rig.clock.advance(timedelta(seconds=20))
    rig.hub.condition_cleared(halted.dedup_key, rig.clock.now())
    rig.clock.advance(timedelta(seconds=20))
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED, at=rig.clock.now()))
    rig.clock.advance(timedelta(seconds=20))
    rig.hub.condition_cleared(halted.dedup_key, rig.clock.now())
    rig.deliver_all()

    received = [
        (i.alert.kind, i.alert.recovery) for i in rig.channels["phone"].received
    ]
    assert received.count((AlertKind.BOT_HALTED, False)) == 2
    assert received.count((AlertKind.BOT_HALTED, True)) == 2
    assert received[-1] == (AlertKind.BOT_HALTED, True)


def test_a_warning_that_comes_back_after_its_recovery_is_sent_again(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path, channel_ids=("phone",))
    exit_ = an_alert(AlertKind.RANGE_EXIT)
    rig.hub.publish(exit_)
    rig.clock.advance(timedelta(minutes=1))
    rig.hub.condition_cleared(exit_.dedup_key, rig.clock.now())

    rig.clock.advance(timedelta(minutes=3))
    rig.hub.publish(an_alert(AlertKind.RANGE_EXIT, at=rig.clock.now()))
    rig.hub.condition_cleared(exit_.dedup_key, rig.clock.now())
    rig.deliver_all()

    received = [i.alert.recovery for i in rig.channels["phone"].received]
    assert received == [False, False, True, True] or sorted(received) == [
        False,
        False,
        True,
        True,
    ]


def _stale_wave(rig, count: int):  # type: ignore[no-untyped-def]
    alerts = [an_alert(FEED, bot_subject(f"bot{n}")) for n in range(count)]
    for alert in alerts:
        rig.hub.publish(alert)
    rig.clock.advance(timedelta(seconds=11))
    rig.hub.flush_due()
    return alerts


def test_a_grouped_feed_alert_recovers_when_its_last_member_clears(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path, channel_ids=("phone",))
    members = _stale_wave(rig, 3)

    for member in members[:2]:
        rig.hub.condition_cleared(member.dedup_key, rig.clock.now())
    rig.deliver_all()
    assert [i.alert.recovery for i in rig.channels["phone"].received] == [False]

    rig.hub.condition_cleared(members[2].dedup_key, rig.clock.now())
    rig.hub.condition_cleared(members[2].dedup_key, rig.clock.now())
    rig.deliver_all()

    [grouped, recovery] = [i.alert for i in rig.channels["phone"].received]
    assert recovery.recovery is True
    assert recovery.kind is FEED
    assert "3 bots" in recovery.title
    assert recovery.subject == grouped.subject


def test_a_new_wave_after_a_grouped_recovery_is_grouped_and_sent_again(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path, channel_ids=("phone",))
    first = _stale_wave(rig, 2)
    for member in first:
        rig.hub.condition_cleared(member.dedup_key, rig.clock.now())

    rig.clock.advance(timedelta(seconds=5))
    _stale_wave(rig, 2)
    rig.deliver_all()

    kinds = [(i.alert.kind, i.alert.recovery) for i in rig.channels["phone"].received]
    assert kinds.count((FEED, False)) == 2
    assert kinds.count((FEED, True)) == 1


def test_feeds_coming_back_are_never_reported_as_a_new_outage(tmp_path: Path) -> None:
    """Three bots go stale far enough apart to be sent alone, then all recover
    inside one grouping window. The owner must read three recoveries, not a
    "Price feed stale: 3 bots" alert at the moment the feeds came back."""
    rig = build_rig(tmp_path, channel_ids=("phone",))
    members = []
    for number in range(3):
        alert = an_alert(FEED, bot_subject(f"bot{number}"))
        members.append(alert)
        rig.hub.publish(alert)
        rig.clock.advance(timedelta(seconds=11))
        rig.hub.flush_due()

    for member in members:
        rig.hub.condition_cleared(member.dedup_key, rig.clock.now())
    rig.clock.advance(timedelta(seconds=11))
    rig.hub.flush_due()
    rig.deliver_all()

    after = [i.alert for i in rig.channels["phone"].received][3:]
    assert len(after) == 3
    assert all(alert.recovery for alert in after)
    assert not any(
        "stale" in alert.title.lower() and not alert.recovery for alert in after
    )
