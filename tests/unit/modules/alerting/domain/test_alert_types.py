"""The typed alert and its catalog (`EPIC-036A`, N1)."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta, timezone

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_catalog import (
    group_of,
    label_of,
    severity_of,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_group import AlertGroup
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
    SubjectScope,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import (
    NOW,
    an_alert,
    bot_subject,
)

REQUIRED_KINDS = {
    "BOT_HALTED",
    "BOT_ERROR",
    "STOP_LOSS_HIT",
    "TAKE_PROFIT_HIT",
    "PRICE_FEED_STALE",
    "USER_STREAM_DOWN",
    "KEY_REJECTED",
    "STORAGE_FAILURE",
    "STOP_FAILED",
    "RATE_LIMITED",
    "RANGE_EXIT",
    "APP_FAILURE",
    "HEARTBEAT",
    "DAILY_SUMMARY",
    "CHANNEL_FAILING",
}


def test_an_alert_is_frozen_and_carries_its_subject() -> None:
    alert = an_alert(AlertKind.STOP_FAILED)

    with pytest.raises(dataclasses.FrozenInstanceError):
        alert.title = "changed"  # type: ignore[misc]

    assert alert.subject == bot_subject()
    assert alert.subject.scope is SubjectScope.BOT
    assert (alert.subject.bot_id, alert.subject.venue, alert.subject.symbol) == (
        "g3n092",
        "spot-mainnet",
        "ETHUSDT",
    )
    assert alert.at == NOW


def test_every_alert_kind_has_one_group_and_one_default_severity() -> None:
    assert {kind.name for kind in AlertKind} >= REQUIRED_KINDS
    for kind in AlertKind:
        assert isinstance(group_of(kind), AlertGroup)
        assert isinstance(severity_of(kind), Severity)
        assert label_of(kind)


def test_a_stop_that_failed_is_critical_and_a_heartbeat_is_not() -> None:
    assert severity_of(AlertKind.STOP_FAILED) is Severity.CRITICAL
    assert severity_of(AlertKind.HEARTBEAT) is Severity.INFO
    assert severity_of(AlertKind.RATE_LIMITED) is Severity.WARNING


def test_severity_orders_critical_above_warning_above_info() -> None:
    assert Severity.CRITICAL > Severity.WARNING > Severity.INFO


def test_a_raised_alert_takes_the_kinds_severity_and_a_key_from_kind_bot_and_reason() -> (
    None
):
    first = an_alert(AlertKind.BOT_HALTED, reason="stop-loss")
    other_bot = an_alert(AlertKind.BOT_HALTED, bot_subject("zzz"), reason="stop-loss")
    other_reason = an_alert(AlertKind.BOT_HALTED, reason="manual")

    assert first.severity is Severity.CRITICAL
    assert len({first.dedup_key, other_bot.dedup_key, other_reason.dedup_key}) == 3
    assert (
        first.dedup_key == an_alert(AlertKind.BOT_HALTED, reason="stop-loss").dedup_key
    )


def test_an_alert_time_must_be_aware() -> None:
    with pytest.raises(ValueError, match="timezone"):
        Alert.raised(
            AlertKind.APP_FAILURE,
            AlertSubject.app(),
            "t",
            "d",
            datetime.fromisoformat("2026-10-13T12:00:00"),
        )


def test_an_aware_time_in_another_zone_is_kept_as_an_instant() -> None:
    plus7 = timezone(timedelta(hours=7))
    alert = Alert.raised(
        AlertKind.APP_FAILURE,
        AlertSubject.app(),
        "t",
        "d",
        datetime(2026, 10, 13, 19, 0, tzinfo=plus7),
    )

    assert alert.at == datetime(2026, 10, 13, 12, 0, tzinfo=UTC)


def test_a_bot_subject_needs_a_bot_and_a_venue_subject_a_venue() -> None:
    with pytest.raises(ValueError, match="bot"):
        AlertSubject.bot("", "name", "spot-grid", "spot-mainnet", "ETHUSDT")
    with pytest.raises(ValueError, match="venue"):
        AlertSubject.venue_wide("")
    assert AlertSubject.app().scope is SubjectScope.APP
