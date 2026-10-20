"""`EPIC-036D2` — what the Alerts screen reads: sent alerts, newest first, and whether a
channel is failing. Real hub, worker and outbox over scripted channels."""

from __future__ import annotations

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
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.delivery_state import (
    DeliveryState,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import (
    FAST,
    Rig,
    an_alert,
    bot_subject,
    build_rig,
)


def _history(rig: Rig) -> OutboxAlertHistory:
    return OutboxAlertHistory(rig.outbox, RegisteredChannelCatalog(rig.channels))


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
