"""The hub keeps a flood down: dedup, grouping, inhibition, recovery, quiet hours."""

from __future__ import annotations

from datetime import time, timedelta
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_clock import (
    FakeAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_settings import (
    AlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.quiet_hours import QuietHours
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import (
    SPOT,
    an_alert,
    at_utc,
    bot_subject,
    build_rig,
)

FEED = AlertKind.PRICE_FEED_STALE


def test_a_repeat_updates_one_record_and_counts(tmp_path: Path) -> None:
    rig = build_rig(tmp_path)

    rig.hub.publish(an_alert())
    rig.clock.advance(timedelta(seconds=30))
    rig.hub.publish(an_alert(at=rig.clock.now()))
    rig.deliver_all()

    history = rig.outbox.history(10)
    assert len(history) == 1
    assert history[0].record.count == 2
    assert [len(c.received) for c in rig.channels.values()] == [1, 1]


def test_a_critical_repeat_after_its_one_minute_window_is_a_new_record(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path)

    rig.hub.publish(an_alert())
    rig.clock.advance(timedelta(seconds=59))
    rig.hub.publish(an_alert(at=rig.clock.now()))
    rig.clock.advance(timedelta(seconds=2))
    rig.hub.publish(an_alert(at=rig.clock.now()))

    assert [e.record.count for e in rig.outbox.history(10)] == [1, 2]


def test_a_warning_repeat_is_held_back_for_fifteen_minutes(tmp_path: Path) -> None:
    rig = build_rig(tmp_path)
    warning = AlertKind.RATE_LIMITED

    rig.hub.publish(an_alert(warning))
    rig.clock.advance(timedelta(minutes=14))
    rig.hub.publish(an_alert(warning, at=rig.clock.now()))
    rig.clock.advance(timedelta(minutes=2))
    rig.hub.publish(an_alert(warning, at=rig.clock.now()))

    assert [e.record.count for e in rig.outbox.history(10)] == [1, 2]


def test_dedup_windows_do_not_survive_a_restart(tmp_path: Path) -> None:
    """The price paid: the windows are in memory. After a restart a repeat is a
    new record, so the owner hears it twice rather than never."""
    first = build_rig(tmp_path)
    first.hub.publish(an_alert())
    first.outbox.close()

    second = build_rig(tmp_path, clock=first.clock)
    second.hub.publish(an_alert(at=second.clock.now()))

    assert len(second.outbox.history(10)) == 2


def test_alerts_of_one_kind_and_venue_coalesce_into_one_message(tmp_path: Path) -> None:
    rig = build_rig(tmp_path)

    for number in range(7):
        rig.hub.publish(an_alert(FEED, bot_subject(f"bot{number}")))
        rig.clock.advance(timedelta(seconds=1))
    rig.hub.flush_due()
    rig.deliver_all()
    assert rig.channels["phone"].received == []  # still inside the 10 s window

    rig.clock.advance(timedelta(seconds=10))
    rig.hub.flush_due()
    rig.deliver_all()

    [grouped] = [item.alert for item in rig.channels["phone"].received]
    assert grouped.kind is FEED
    assert "7 bots" in grouped.title
    assert SPOT in grouped.title
    assert all(f"bot bot{number}" in grouped.detail for number in range(7))
    assert len(rig.outbox.history(10)) == 1


def test_a_lone_alert_leaves_the_window_unchanged(tmp_path: Path) -> None:
    rig = build_rig(tmp_path)
    alert = an_alert(FEED)

    rig.hub.publish(alert)
    rig.clock.advance(timedelta(seconds=11))
    rig.hub.flush_due()
    rig.deliver_all()

    assert [item.alert for item in rig.channels["phone"].received] == [alert]


def test_two_venues_make_two_grouped_messages(tmp_path: Path) -> None:
    rig = build_rig(tmp_path, channel_ids=("phone",))

    for venue in (SPOT, "futures-mainnet"):
        for number in range(2):
            rig.hub.publish(an_alert(FEED, bot_subject(f"{venue}{number}", venue)))
    rig.clock.advance(timedelta(seconds=11))
    rig.hub.flush_due()
    rig.deliver_all()

    titles = sorted(item.alert.title for item in rig.channels["phone"].received)
    assert len(titles) == 2
    assert all("2 bots" in title for title in titles)


def test_a_venue_down_alert_inhibits_the_per_bot_feed_stale_alerts(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path, channel_ids=("phone",))
    venue_down = an_alert(AlertKind.USER_STREAM_DOWN, AlertSubject.venue_wide(SPOT))

    rig.hub.publish(venue_down)
    for number in range(3):
        rig.hub.publish(an_alert(FEED, bot_subject(f"bot{number}")))
    rig.hub.publish(an_alert(FEED, bot_subject("elsewhere", "futures-mainnet")))
    rig.clock.advance(timedelta(seconds=11))
    rig.hub.flush_due()
    rig.deliver_all()

    kinds = rig.received_kinds("phone")
    assert kinds.count(AlertKind.USER_STREAM_DOWN) == 1
    assert kinds.count(FEED) == 1  # only the other venue's bot
    assert rig.hub.suppressed_count(venue_down.dedup_key) == 3


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


def _quiet_rig(tmp_path: Path):  # type: ignore[no-untyped-def]
    rig = build_rig(tmp_path, clock=FakeAlertClock(at_utc(23, 30)))
    rig.settings.replace(AlertSettings(quiet_hours=QuietHours(time(23, 0), time(7, 0))))
    return rig


def test_quiet_hours_hold_info_and_warning_but_never_critical(tmp_path: Path) -> None:
    rig = _quiet_rig(tmp_path)

    rig.hub.publish(an_alert(AlertKind.RATE_LIMITED, at=rig.clock.now()))
    rig.hub.publish(
        an_alert(AlertKind.HEARTBEAT, AlertSubject.app(), at=rig.clock.now())
    )
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED, at=rig.clock.now()))
    rig.deliver_all()

    assert rig.received_kinds("phone") == [AlertKind.BOT_HALTED]


def test_held_alerts_are_released_as_one_summary_when_the_period_ends(
    tmp_path: Path,
) -> None:
    rig = _quiet_rig(tmp_path)
    rig.hub.publish(an_alert(AlertKind.RATE_LIMITED, at=rig.clock.now()))
    rig.hub.publish(
        an_alert(AlertKind.HEARTBEAT, AlertSubject.app(), at=rig.clock.now())
    )

    rig.clock.advance(timedelta(hours=5))  # 04:30, still quiet
    rig.hub.flush_due()
    rig.deliver_all()
    assert rig.received_kinds("phone") == []

    rig.clock.advance(timedelta(hours=2, minutes=31))  # 07:01
    rig.hub.flush_due()
    rig.hub.flush_due()
    rig.deliver_all()

    [summary] = [item.alert for item in rig.channels["phone"].received]
    assert summary.kind is AlertKind.DAILY_SUMMARY
    assert "2 alerts" in summary.title
    assert "RATE_LIMITED" in summary.detail or "Rate limited" in summary.detail


def test_publishing_never_calls_a_channel(tmp_path: Path) -> None:
    """The caller's thread only writes the outbox; a slow channel cannot hold it."""
    rig = build_rig(tmp_path)

    rig.hub.publish(an_alert())

    assert [c.received for c in rig.channels.values()] == [[], []]
    assert rig.wakeup.calls == 1


def test_an_alert_the_hub_receives_is_recorded_even_when_no_route_delivers_it(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path, channel_ids=())

    rig.hub.publish(an_alert())

    [entry] = rig.outbox.history(10)
    assert entry.deliveries == ()
    assert entry.record.alert.kind is AlertKind.BOT_HALTED
