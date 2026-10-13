"""What the owner configures: routes, per-bot modes, quiet hours (N4, N5)."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, time, timedelta, timezone

from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_group import AlertGroup
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_route import AlertRoute
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_settings import (
    AlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.bot_alert_mode import (
    BotAlertMode,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.quiet_hours import QuietHours
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity

FORBIDDEN_WORDS = ("secret", "token", "webhook", "password", "key", "url")


def test_without_a_route_critical_is_loud_and_the_rest_are_silent() -> None:
    settings = AlertSettings()

    assert (
        settings.loudness_for(AlertGroup.BOT_EVENTS, "phone", Severity.CRITICAL)
        is Loudness.LOUD
    )
    assert (
        settings.loudness_for(AlertGroup.NOTICES, "phone", Severity.WARNING)
        is Loudness.SILENT
    )
    assert (
        settings.loudness_for(AlertGroup.ROUTINE, "phone", Severity.INFO)
        is Loudness.SILENT
    )


def test_a_route_cell_overrides_the_default_for_its_group_and_channel_only() -> None:
    settings = AlertSettings(
        routes=(AlertRoute(AlertGroup.NOTICES, "backup", Loudness.OFF),)
    )

    assert (
        settings.loudness_for(AlertGroup.NOTICES, "backup", Severity.WARNING)
        is Loudness.OFF
    )
    assert (
        settings.loudness_for(AlertGroup.NOTICES, "phone", Severity.WARNING)
        is Loudness.SILENT
    )
    assert (
        settings.loudness_for(AlertGroup.BOT_EVENTS, "backup", Severity.CRITICAL)
        is Loudness.LOUD
    )


def test_a_bot_is_on_unless_the_owner_set_it() -> None:
    settings = AlertSettings(bot_modes={"quiet-bot": BotAlertMode.OFF})

    assert settings.mode_of("quiet-bot") is BotAlertMode.OFF
    assert settings.mode_of("any-other") is BotAlertMode.ON


def test_no_secret_is_stored_in_the_settings() -> None:
    """A channel reads its secret by name when it sends; the settings hold none."""
    seen: list[str] = []

    def collect(cls: type) -> None:
        for field in dataclasses.fields(cls):
            seen.append(field.name)

    for cls in (AlertSettings, AlertRoute, QuietHours):
        collect(cls)

    assert seen
    assert not [name for name in seen if any(word in name for word in FORBIDDEN_WORDS)]


def test_quiet_hours_wrap_midnight() -> None:
    night = QuietHours(time(23, 0), time(7, 0))

    assert night.contains(datetime(2026, 10, 13, 23, 30, tzinfo=UTC))
    assert night.contains(datetime(2026, 10, 14, 6, 59, tzinfo=UTC))
    assert not night.contains(datetime(2026, 10, 14, 7, 0, tzinfo=UTC))
    assert not night.contains(datetime(2026, 10, 13, 22, 59, tzinfo=UTC))


def test_quiet_hours_are_read_in_their_own_zone() -> None:
    plus7 = QuietHours(time(23, 0), time(7, 0), timezone(timedelta(hours=7)))

    assert plus7.contains(datetime(2026, 10, 13, 17, 0, tzinfo=UTC))  # 00:00 local
    assert not plus7.contains(datetime(2026, 10, 13, 12, 0, tzinfo=UTC))  # 19:00 local


def test_quiet_hours_of_the_same_start_and_end_are_never_quiet() -> None:
    assert not QuietHours(time(8, 0), time(8, 0)).contains(
        datetime(2026, 10, 13, 8, 0, tzinfo=UTC)
    )
