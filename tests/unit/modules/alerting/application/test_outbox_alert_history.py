"""`EPIC-036D2` — what the Alerts screen reads: sent alerts, newest first, and whether a
channel is failing. Real hub, worker and outbox over scripted channels."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.registered_channel_catalog import (
    RegisteredChannelCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.outbox_alert_history import (
    APP_SUBJECT,
    OutboxAlertHistory,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.delivery_result import (
    DeliveryResult,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_settings import (
    AlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.delivery_state import (
    DeliveryState,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import (
    FAST,
    Rig,
    an_alert,
    bot_subject,
    build_rig,
)


def _history(rig: Rig) -> OutboxAlertHistory:
    return OutboxAlertHistory(
        rig.outbox, RegisteredChannelCatalog(rig.channels), rig.settings
    )


def test_a_sent_alert_is_listed_with_where_it_went(tmp_path: Path) -> None:
    rig = build_rig(tmp_path, ("phone",))
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
    rig.deliver_all()

    report = _history(rig).read(50)

    (row,) = report.rows
    assert row.kind is AlertKind.BOT_HALTED
    assert row.subject == "bot g3n092"
    assert [(o.channel_id, o.state) for o in row.outcomes] == [
        ("phone", DeliveryState.SENT)
    ]
    assert [(c.channel_id, c.failing, c.waiting) for c in report.channels] == [
        ("phone", False, 0)
    ]


def test_the_newest_alert_comes_first(tmp_path: Path) -> None:
    rig = build_rig(tmp_path, ("phone",))
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED, bot_subject("aaaaaa")))
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED, bot_subject("bbbbbb")))

    subjects = [row.subject for row in _history(rig).read(50).rows]

    assert subjects == ["bot bbbbbb", "bot aaaaaa"]


def test_an_alert_about_the_app_or_a_venue_is_named_for_it(tmp_path: Path) -> None:
    rig = build_rig(tmp_path, ("phone",))
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED, AlertSubject.app()))
    rig.hub.publish(
        an_alert(AlertKind.BOT_HALTED, AlertSubject.venue_wide("spot-mainnet"))
    )

    subjects = [row.subject for row in _history(rig).read(50).rows]

    assert subjects == ["spot-mainnet", APP_SUBJECT]


def test_a_channel_whose_newest_try_failed_is_failing(tmp_path: Path) -> None:
    rig = build_rig(tmp_path, ("phone", "backup"), delivery_policy=FAST)
    rig.channels["phone"].script.append(DeliveryResult.refused("refused"))
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
    rig.deliver_all()

    channels = {c.channel_id: c for c in _history(rig).read(50).channels}

    assert channels["phone"].failing
    assert not channels["backup"].failing


def test_a_channel_that_recovered_is_not_failing(tmp_path: Path) -> None:
    rig = build_rig(tmp_path, ("phone",), delivery_policy=FAST)
    rig.channels["phone"].script.append(DeliveryResult.refused("refused"))
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED, bot_subject("aaaaaa")))
    rig.deliver_all()
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED, bot_subject("bbbbbb")))
    rig.deliver_all()

    (channel,) = _history(rig).read(50).channels

    assert not channel.failing


def test_a_channel_with_no_alerts_yet_is_not_failing(tmp_path: Path) -> None:
    rig = build_rig(tmp_path, ("phone",))

    report = _history(rig).read(50)

    assert report.rows == ()
    assert [c.failing for c in report.channels] == [False]


def _fail_then_publish(rig: Rig, second: AlertKind, first: AlertKind) -> None:
    """One alert the channel refused, then a newer one that has not been tried."""
    rig.channels["phone"].script.append(DeliveryResult.refused("refused"))
    rig.hub.publish(an_alert(first, bot_subject("aaaaaa")))
    rig.deliver_all()
    rig.hub.publish(an_alert(second, bot_subject("bbbbbb")))


def test_a_newer_alert_still_waiting_does_not_hide_a_failure(tmp_path: Path) -> None:
    rig = build_rig(tmp_path, ("phone",), delivery_policy=FAST)
    _fail_then_publish(rig, AlertKind.BOT_HALTED, AlertKind.BOT_HALTED)

    (channel,) = _history(rig).read(50).channels

    assert channel.failing
    assert channel.waiting == 1


def test_a_newer_alert_the_queue_dropped_does_not_hide_a_failure(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path, ("phone",), delivery_policy=FAST)
    _fail_then_publish(rig, AlertKind.ORDER_FILLED, AlertKind.BOT_HALTED)
    assert rig.outbox.shed_lowest("phone", Severity.CRITICAL)

    report = _history(rig).read(50)

    assert DeliveryState.DROPPED in [o.state for r in report.rows for o in r.outcomes]
    assert report.channels[0].failing


def test_a_try_that_failed_and_will_be_tried_again_is_failing(tmp_path: Path) -> None:
    rig = build_rig(tmp_path, ("phone",), delivery_policy=FAST)
    rig.channels["phone"].script.append(DeliveryResult.failed("timeout"))
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
    rig.deliver_all()

    report = _history(rig).read(50)

    assert [o.state for o in report.rows[0].outcomes] == [DeliveryState.RETRYING]
    assert report.channels[0].failing


def test_a_wait_the_platform_or_the_pacing_asked_for_is_not_a_failure(
    tmp_path: Path,
) -> None:
    """A burst is spread by `PacedChannel` as `retry_later`: RETRYING with no attempt used."""
    rig = build_rig(tmp_path, ("phone",), delivery_policy=FAST)
    rig.channels["phone"].script.append(
        DeliveryResult.retry_later(timedelta(seconds=2), "pacing")
    )
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
    rig.deliver_all()

    report = _history(rig).read(50)

    assert [o.state for o in report.rows[0].outcomes] == [DeliveryState.RETRYING]
    assert not report.channels[0].failing


def test_a_delivery_that_expired_is_failing(tmp_path: Path) -> None:
    rig = build_rig(tmp_path, ("phone",), delivery_policy=FAST)
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
    assert rig.outbox.expire_before(rig.clock.now() + timedelta(hours=1)) == 1

    report = _history(rig).read(50)

    assert [o.state for o in report.rows[0].outcomes] == [DeliveryState.EXPIRED]
    assert report.channels[0].failing


def test_the_time_shown_is_when_the_alert_was_first_raised_so_the_rows_stay_in_order(
    tmp_path: Path,
) -> None:
    """A repeat is counted, not re-listed: the older alert must not show a later time than the
    newer one above it."""
    rig = build_rig(tmp_path, ("phone",))
    first = an_alert(AlertKind.BOT_HALTED, bot_subject("aaaaaa"), at=rig.clock.now())
    rig.hub.publish(first)
    rig.clock.advance(timedelta(seconds=20))
    rig.hub.publish(
        an_alert(AlertKind.BOT_HALTED, bot_subject("bbbbbb"), at=rig.clock.now())
    )
    rig.clock.advance(timedelta(seconds=20))
    rig.hub.publish(first)  # the same condition again: bumped, not stored twice

    rows = _history(rig).read(50).rows

    assert [r.subject for r in rows] == ["bot bbbbbb", "bot aaaaaa"]
    assert rows[0].at > rows[1].at
    assert rows[1].count == 2


def test_a_dead_channel_stays_failing_however_many_alerts_queue_behind_it(
    tmp_path: Path,
) -> None:
    """`EPIC-036D3` review: a channel's health was read from the newest N alerts, so a
    retrying head with 50 or more alerts queued behind it fell out of a small window and the
    indicator said `ok` while the channel was dark. Health is the channel's own newest real
    delivery, whatever the window."""
    rig = build_rig(tmp_path, ("phone",), delivery_policy=FAST)
    rig.channels["phone"].script.append(DeliveryResult.failed("timeout"))
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED, bot_subject("aaaaaa")))
    rig.deliver_all()  # the head: RETRYING after a real failed try; the channel now waits
    for number in range(60):
        rig.hub.publish(an_alert(AlertKind.BOT_HALTED, bot_subject(f"q{number:05d}")))

    for limit in (1, 5, 500):
        report = _history(rig).read(limit)

        assert report.channels[0].failing, f"read({limit})"
        assert report.channels[0].waiting == 61, f"read({limit})"


def test_the_health_is_the_same_whatever_the_window_when_nothing_is_wrong(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path, ("phone",))
    for number in range(8):
        rig.hub.publish(an_alert(AlertKind.BOT_HALTED, bot_subject(f"q{number:05d}")))
    rig.deliver_all()

    assert [_history(rig).read(limit).channels for limit in (1, 500)] == [
        _history(rig).read(500).channels
    ] * 2


def test_a_channel_the_owner_switched_off_is_never_failing_and_says_it_is_off(
    tmp_path: Path,
) -> None:
    """Review of PR #672: the status bar must see the switch (`EPIC-036D8`)."""
    rig = build_rig(tmp_path, ("phone", "backup"), delivery_policy=FAST)
    rig.channels["phone"].script.append(DeliveryResult.refused("refused"))
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
    rig.deliver_all()
    rig.settings.replace(AlertSettings(disabled_channels=frozenset({"phone"})))

    channels = {c.channel_id: c for c in _history(rig).read(50).channels}

    assert not channels["phone"].enabled and not channels["phone"].failing
    assert channels["backup"].enabled
