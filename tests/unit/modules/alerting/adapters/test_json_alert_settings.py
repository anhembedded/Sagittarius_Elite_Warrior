"""`BOT-191` — what the owner set per bot survives a restart, and a file that is missing,
older, newer or damaged never stops the app or silences a bot.

Real files under `tmp_path`; nothing is doubled.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.json_alert_settings import (
    SETTINGS_SCHEMA,
    JsonAlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_quiet_hours_setting import (
    QuietHoursChoice,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.bot_alert_mode import (
    BotAlertMode as Mode,
)


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "state" / "alert_settings.json"


def _write(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def test_no_file_is_every_default_and_creates_none(
    path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    settings = JsonAlertSettings(path)

    assert settings.modes() == {}
    assert settings.current().mode_of("g3n092") is Mode.ON
    assert not path.exists()
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


def test_a_mode_set_survives_a_restart(path: Path) -> None:
    JsonAlertSettings(path).set_mode("g3n092", Mode.CRITICAL_ONLY)
    JsonAlertSettings(path).set_mode("zz9999", Mode.OFF)

    restarted = JsonAlertSettings(path)

    assert restarted.current().mode_of("g3n092") is Mode.CRITICAL_ONLY
    assert restarted.current().mode_of("zz9999") is Mode.OFF
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "schema": SETTINGS_SCHEMA,
        "bot_modes": {"g3n092": "critical_only", "zz9999": "off"},
    }
    assert not path.with_name(path.name + ".tmp").exists()


def test_setting_a_bot_back_to_on_forgets_it(path: Path) -> None:
    settings = JsonAlertSettings(path)
    settings.set_mode("g3n092", Mode.OFF)

    settings.set_mode("g3n092", Mode.ON)

    assert JsonAlertSettings(path).modes() == {}
    assert json.loads(path.read_text(encoding="utf-8"))["bot_modes"] == {}


@pytest.mark.parametrize(
    "document",
    [
        ["not", "an", "object"],
        {"bot_modes": {"g3n092": "off"}},  # no schema: older than this format
        {"schema": "sew.alert-settings/2", "bot_modes": {"g3n092": "off"}},  # newer
        {"schema": SETTINGS_SCHEMA, "bot_modes": ["g3n092"]},
    ],
)
def test_a_file_of_another_shape_is_every_default_told_once_and_kept_aside_on_the_next_save(
    path: Path, caplog: pytest.LogCaptureFixture, document: object
) -> None:
    _write(path, document)
    original = path.read_text(encoding="utf-8")
    caplog.set_level(logging.DEBUG)

    settings = JsonAlertSettings(path)

    assert settings.current().mode_of("g3n092") is Mode.ON
    [warning] = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert "[alert-settings]" in warning.getMessage()
    assert path.read_text(encoding="utf-8") == original

    settings.set_mode("zz9999", Mode.OFF)

    assert (
        path.with_name(path.name + ".unreadable").read_text(encoding="utf-8")
        == original
    )
    assert JsonAlertSettings(path).modes() == {"zz9999": Mode.OFF}


def test_a_file_that_is_not_json_is_every_default(
    path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\xff\xfe not json {")
    caplog.set_level(logging.DEBUG)

    settings = JsonAlertSettings(path)

    assert settings.modes() == {}
    assert len([r for r in caplog.records if r.levelno >= logging.WARNING]) == 1


def test_one_mode_this_build_does_not_know_is_skipped_and_the_rest_kept(
    path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _write(
        path,
        {
            "schema": SETTINGS_SCHEMA,
            "bot_modes": {"g3n092": "critical_only", "zz9999": "digest_hourly"},
        },
    )
    caplog.set_level(logging.DEBUG)

    settings = JsonAlertSettings(path)

    assert settings.modes() == {"g3n092": Mode.CRITICAL_ONLY}
    assert len([r for r in caplog.records if r.levelno >= logging.WARNING]) == 1


def test_a_read_only_copy_refuses_the_change_and_writes_nothing(path: Path) -> None:
    """Its alerting never runs, so a choice kept there would reach nothing and only look saved."""
    settings = JsonAlertSettings(path, read_only=True)

    with pytest.raises(PermissionError):
        settings.set_mode("g3n092", Mode.OFF)

    assert settings.read_only is True
    assert settings.current().mode_of("g3n092") is Mode.ON
    assert not path.exists()


def test_a_write_that_fails_changes_nothing_in_memory(path: Path) -> None:
    path.parent.parent.mkdir(parents=True, exist_ok=True)
    path.parent.write_text("a file where the state folder goes", encoding="utf-8")
    settings = JsonAlertSettings(path)

    with pytest.raises(OSError):
        settings.set_mode("g3n092", Mode.OFF)

    assert settings.current().mode_of("g3n092") is Mode.ON


def test_a_failed_write_leaves_no_temporary_file_and_keeps_the_old_one(
    path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = JsonAlertSettings(path)
    settings.set_mode("g3n092", Mode.CRITICAL_ONLY)

    def refuse(_source: object, _target: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("os.replace", refuse)
    with pytest.raises(OSError):
        settings.set_mode("zz9999", Mode.OFF)

    assert settings.modes() == {"g3n092": Mode.CRITICAL_ONLY}
    assert JsonAlertSettings(path).modes() == {"g3n092": Mode.CRITICAL_ONLY}
    assert not path.with_name(path.name + ".tmp").exists()


def test_two_members_of_one_name_are_not_trusted(path: Path) -> None:
    """`json.loads` would keep the last: a hand-edited file that says two things is not read."""
    path.parent.mkdir(parents=True)
    path.write_text(
        '{"schema": "sew.alert-settings/1", "bot_modes": '
        '{"g3n092": "on", "g3n092": "off"}}',
        encoding="utf-8",
    )

    assert JsonAlertSettings(path).modes() == {}


@pytest.mark.parametrize(
    "text",
    [
        "[" * 100_000,
        '{"schema": "sew.alert-settings/1", "bot_modes": {"g3n092": ["off"]}}',
    ],
)
def test_nothing_in_a_file_makes_startup_raise(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")

    assert JsonAlertSettings(path).modes() == {}


def test_a_second_unreadable_file_does_not_replace_the_first_kept_one(
    path: Path,
) -> None:
    path.parent.mkdir(parents=True)
    path.write_text("garbage one", encoding="utf-8")
    JsonAlertSettings(path).set_mode("g3n092", Mode.OFF)
    path.write_text("garbage two", encoding="utf-8")

    JsonAlertSettings(path).set_mode("zz9999", Mode.OFF)

    kept = sorted(
        p.read_text(encoding="utf-8") for p in path.parent.glob("*.unreadable*")
    )
    assert kept == ["garbage one", "garbage two"]


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
