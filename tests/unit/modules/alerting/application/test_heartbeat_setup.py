"""`EPIC-036D9` — choosing the heartbeat's interval: only the offered hours, the default keeps no
value, a store that cannot write is told, a read-only copy changes nothing. A real
`JsonAlertSettings` under `tmp_path`; nothing is doubled."""

from __future__ import annotations

from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.json_alert_settings import (
    JsonAlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.heartbeat_setup import (
    DEFAULT_HOURS,
    HeartbeatSave,
    HeartbeatSetup,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_policies import (
    HEARTBEAT_HOURS_CHOICES,
)


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "state" / "alert_settings.json"


def test_nothing_chosen_shows_the_default_and_the_choices(path: Path) -> None:
    state = HeartbeatSetup(JsonAlertSettings(path)).state()

    assert state.hours == DEFAULT_HOURS == 6
    assert state.choices == HEARTBEAT_HOURS_CHOICES
    assert state.editable


def test_every_offered_interval_is_kept_and_shown(path: Path) -> None:
    settings = JsonAlertSettings(path)
    setup = HeartbeatSetup(settings)

    for hours in HEARTBEAT_HOURS_CHOICES:
        outcome = setup.set_hours(hours)

        assert setup.state().hours == hours
        assert outcome is (
            HeartbeatSave.BACK_TO_DEFAULT
            if hours == DEFAULT_HOURS
            else HeartbeatSave.SAVED
        )


def test_choosing_the_default_keeps_no_value_so_a_later_default_still_reaches_the_owner(
    path: Path,
) -> None:
    settings = JsonAlertSettings(path)
    setup = HeartbeatSetup(settings)
    setup.set_hours(12)

    setup.set_hours(DEFAULT_HOURS)

    assert settings.heartbeat_hours() is None


@pytest.mark.parametrize("hours", [0, 4, 7, 25, -1], ids=repr)
def test_an_interval_that_is_not_offered_is_refused_and_nothing_is_kept(
    path: Path, hours: int
) -> None:
    settings = JsonAlertSettings(path)

    outcome = HeartbeatSetup(settings).set_hours(hours)

    assert outcome is HeartbeatSave.NOT_A_CHOICE
    assert settings.heartbeat_hours() is None
    assert not path.exists()


def test_a_read_only_copy_changes_nothing_and_says_so(path: Path) -> None:
    setup = HeartbeatSetup(JsonAlertSettings(path, read_only=True))

    assert setup.set_hours(12) is HeartbeatSave.READ_ONLY
    assert not setup.state().editable
    assert not path.exists()


def test_a_store_that_cannot_write_is_told_not_reported_saved(path: Path) -> None:
    settings = JsonAlertSettings(path)
    path.parent.mkdir(parents=True)
    path.mkdir()  # the file's place is a folder: the write raises OSError

    outcome = HeartbeatSetup(settings).set_hours(12)

    assert outcome is HeartbeatSave.NOT_KEPT
    assert settings.heartbeat_hours() is None
