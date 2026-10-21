"""`EPIC-036D6` — the quiet hours survive a restart and reach the hub as a zone-aware period (or the machine's clock); a bad entry is off, never a hold. Real files under `tmp_path`."""

from __future__ import annotations

import json
import logging
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.json_alert_settings import (
    JsonAlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.settings_document import (
    SETTINGS_SCHEMA,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_quiet_hours_setting import (
    QuietHoursChoice,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_group import AlertGroup
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.bot_alert_mode import (
    BotAlertMode as Mode,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "state" / "alert_settings.json"


def _write(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def test_quiet_hours_survive_a_restart_and_reach_the_hub_as_a_zone_aware_period(
    path: Path,
) -> None:
    """`EPIC-036D6`: the choice is kept as text and the hub reads a `QuietHours` in that zone."""
    JsonAlertSettings(path).set_quiet_hours(
        QuietHoursChoice(time(22, 0), time(7, 0), "Europe/Berlin")
    )

    again = JsonAlertSettings(path)

    assert again.quiet_hours() == QuietHoursChoice(
        time(22, 0), time(7, 0), "Europe/Berlin"
    )
    quiet = again.current().quiet_hours
    assert quiet is not None
    assert quiet.contains(
        datetime(2026, 1, 15, 22, 30, tzinfo=ZoneInfo("Europe/Berlin"))
    )
    assert not quiet.contains(
        datetime(2026, 1, 15, 12, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    )


def test_setting_a_bots_mode_keeps_the_quiet_hours_and_the_other_way_round(
    path: Path,
) -> None:
    settings = JsonAlertSettings(path)
    settings.set_quiet_hours(QuietHoursChoice(time(23, 0), time(6, 0), "UTC"))

    settings.set_mode("g3n092", Mode.OFF)
    settings.set_quiet_hours(QuietHoursChoice(time(22, 0), time(6, 0), "UTC"))

    again = JsonAlertSettings(path)
    assert again.current().mode_of("g3n092") is Mode.OFF
    assert again.quiet_hours() == QuietHoursChoice(time(22, 0), time(6, 0), "UTC")


def test_removing_the_quiet_hours_forgets_them(path: Path) -> None:
    settings = JsonAlertSettings(path)
    settings.set_quiet_hours(QuietHoursChoice(time(22, 0), time(6, 0), "UTC"))

    settings.set_quiet_hours(None)

    assert "quiet_hours" not in json.loads(path.read_text(encoding="utf-8"))
    assert JsonAlertSettings(path).current().quiet_hours is None


@pytest.mark.parametrize(
    "entry",
    [
        {"start": "25:00", "end": "07:00", "zone": "UTC"},
        {"start": "22:00", "end": "07:00", "zone": "Mars/Olympus"},
        {"start": "22:00", "end": "07:00"},
        ["22:00", "07:00"],
    ],
    ids=["bad-time", "bad-zone", "missing-member", "wrong-shape"],
)
def test_a_quiet_hours_entry_this_build_cannot_read_is_off_told_and_the_modes_kept(
    path: Path, entry: object, caplog: pytest.LogCaptureFixture
) -> None:
    """Off is the safe side: a bad entry never holds an alert back."""
    _write(
        path,
        {
            "schema": SETTINGS_SCHEMA,
            "bot_modes": {"g3n092": "off"},
            "quiet_hours": entry,
        },
    )

    with caplog.at_level(logging.WARNING, logger="App.Alerting"):
        settings = JsonAlertSettings(path)

    assert settings.current().quiet_hours is None
    assert settings.current().mode_of("g3n092") is Mode.OFF
    assert len([r for r in caplog.records if "quiet hours" in r.getMessage()]) == 1


def test_a_read_only_copy_refuses_a_quiet_hours_change(path: Path) -> None:
    settings = JsonAlertSettings(path, read_only=True)

    with pytest.raises(PermissionError):
        settings.set_quiet_hours(QuietHoursChoice(time(22, 0), time(6, 0), "UTC"))

    assert not path.exists()


def test_the_machines_own_clock_is_kept_as_system_and_reaches_the_hub_without_a_name(
    path: Path,
) -> None:
    """`SYSTEM` has no IANA key to store (review of PR #666): it stays the word `SYSTEM`, the
    hub is handed a period read on the machine's clock, and `current()` never raises."""
    settings = JsonAlertSettings(path)

    settings.set_quiet_hours(QuietHoursChoice(time(22, 0), time(7, 0), "SYSTEM"))

    assert JsonAlertSettings(path).quiet_hours() == QuietHoursChoice(
        time(22, 0), time(7, 0), "SYSTEM"
    )
    quiet = settings.current().quiet_hours
    assert quiet is not None and quiet.zone is None


def test_a_name_that_is_no_zone_is_refused_before_anything_is_written(
    path: Path,
) -> None:
    settings = JsonAlertSettings(path)

    with pytest.raises(ValueError):
        settings.set_quiet_hours(
            QuietHoursChoice(time(22, 0), time(7, 0), "ICT, UTC+07:00")
        )

    assert settings.quiet_hours() is None
    assert not path.exists()


def test_the_hubs_view_never_raises_even_if_a_bad_name_got_in(path: Path) -> None:
    """The hub asks for every alert, Critical included: a name that is no zone is off."""
    settings = JsonAlertSettings(path)
    settings._quiet = QuietHoursChoice(time(22, 0), time(7, 0), "Not/AZone")

    assert settings.current().quiet_hours is None


def test_routes_modes_and_quiet_hours_are_written_together_and_none_costs_another(
    path: Path,
) -> None:
    settings = JsonAlertSettings(path)
    settings.set_quiet_hours(QuietHoursChoice(time(22, 0), time(7, 0), "UTC"))
    settings.set_mode("g3n092", Mode.OFF)
    settings.set_route(AlertGroup.ROUTINE, "discord", Loudness.OFF)

    again = JsonAlertSettings(path)

    assert again.quiet_hours() is not None
    assert again.current().mode_of("g3n092") is Mode.OFF
    assert len(again.routes()) == 1
