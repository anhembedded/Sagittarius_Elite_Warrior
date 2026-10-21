"""`EPIC-036D6` — choosing the quiet hours: the period is kept in the display zone as it is at
the time of saving, an empty period is refused, and a store that cannot keep is told, never
reported as saved. A real `JsonAlertSettings` under `tmp_path`; nothing is doubled."""

from __future__ import annotations

import logging
from datetime import time
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.json_alert_settings import (
    JsonAlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.quiet_hours_setup import (
    DEFAULT_END,
    DEFAULT_START,
    QuietHoursSave,
    QuietHoursSetup,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_quiet_hours_setting import (
    QuietHoursChoice,
)


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "state" / "alert_settings.json"


def _setup(settings: JsonAlertSettings, zone: str = "UTC") -> QuietHoursSetup:
    return QuietHoursSetup(settings, lambda: zone)


def test_nothing_set_shows_a_night_off_in_the_zone_a_save_would_use(path: Path) -> None:
    state = _setup(JsonAlertSettings(path), "Europe/Berlin").state()

    assert (state.enabled, state.start, state.end) == (
        False,
        DEFAULT_START,
        DEFAULT_END,
    )
    assert state.zone_key == "Europe/Berlin"
    assert state.editable


def test_a_period_is_kept_in_the_zone_of_the_moment_it_was_saved(path: Path) -> None:
    settings = JsonAlertSettings(path)

    outcome = _setup(settings, "Europe/Berlin").set_period(time(23, 0), time(6, 30))

    assert outcome is QuietHoursSave.SAVED
    assert settings.quiet_hours() == QuietHoursChoice(
        time(23, 0), time(6, 30), "Europe/Berlin"
    )
    # A later change of the display zone does not move the night already set.
    state = _setup(settings, "Asia/Tokyo").state()
    assert state.enabled and state.zone_key == "Europe/Berlin"


def test_the_same_start_and_end_is_refused_and_nothing_is_kept(path: Path) -> None:
    settings = JsonAlertSettings(path)

    outcome = _setup(settings).set_period(time(22, 0), time(22, 0))

    assert outcome is QuietHoursSave.NO_PERIOD
    assert settings.quiet_hours() is None
    assert not path.exists()


def test_turning_off_forgets_the_period(path: Path) -> None:
    settings = JsonAlertSettings(path)
    _setup(settings).set_period(time(22, 0), time(7, 0))

    outcome = _setup(settings).turn_off()

    assert outcome is QuietHoursSave.TURNED_OFF
    assert settings.quiet_hours() is None


def test_a_read_only_copy_changes_nothing_and_says_so(path: Path) -> None:
    settings = JsonAlertSettings(path, read_only=True)
    setup = _setup(settings)

    assert setup.set_period(time(22, 0), time(7, 0)) is QuietHoursSave.READ_ONLY
    assert setup.turn_off() is QuietHoursSave.READ_ONLY
    assert not setup.state().editable
    assert not path.exists()


def test_a_store_that_cannot_write_is_told_not_reported_saved(
    path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    settings = JsonAlertSettings(path)
    path.parent.mkdir(parents=True)
    path.mkdir()  # the file's place is a folder: the write raises OSError

    with caplog.at_level(logging.WARNING, logger="App.Alerting"):
        outcome = _setup(settings).set_period(time(22, 0), time(7, 0))

    assert outcome is QuietHoursSave.NOT_KEPT
    assert settings.quiet_hours() is None
    assert any("could not be kept" in r.getMessage() for r in caplog.records)
