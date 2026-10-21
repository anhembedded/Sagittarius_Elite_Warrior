"""`EPIC-036D9` — the heartbeat's interval survives a restart and reaches the heartbeat; a value
this build does not offer is the default again, told once. Real files under `tmp_path`."""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.json_alert_settings import (
    JsonAlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.settings_document import (
    SETTINGS_SCHEMA,
)


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "state" / "alert_settings.json"


def _write(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def test_nothing_chosen_is_no_interval_so_the_policys_own_applies(path: Path) -> None:
    settings = JsonAlertSettings(path)

    assert settings.heartbeat_hours() is None
    assert settings.current().heartbeat_every is None


def test_a_chosen_interval_survives_a_restart_and_the_heartbeat_sees_it(
    path: Path,
) -> None:
    JsonAlertSettings(path).set_heartbeat_hours(12)

    again = JsonAlertSettings(path)

    assert again.heartbeat_hours() == 12
    assert again.current().heartbeat_every == timedelta(hours=12)


def test_putting_it_back_removes_the_key_from_the_file(path: Path) -> None:
    settings = JsonAlertSettings(path)
    settings.set_heartbeat_hours(12)

    settings.set_heartbeat_hours(None)

    assert "heartbeat_hours" not in json.loads(path.read_text(encoding="utf-8"))
    assert JsonAlertSettings(path).heartbeat_hours() is None


def test_the_interval_is_written_beside_the_other_settings_and_costs_none(
    path: Path,
) -> None:
    settings = JsonAlertSettings(path)
    settings.disable("telegram")

    settings.set_heartbeat_hours(2)

    again = JsonAlertSettings(path)
    assert again.disabled() == {"telegram"} and again.heartbeat_hours() == 2


@pytest.mark.parametrize(
    "value", [5, 0, -6, 6.0, "6", True, None, [6]], ids=lambda v: repr(v)
)
def test_a_value_this_build_does_not_offer_is_the_default_told_once(
    path: Path, caplog: pytest.LogCaptureFixture, value: object
) -> None:
    _write(path, {"schema": SETTINGS_SCHEMA, "bot_modes": {}, "heartbeat_hours": value})

    with caplog.at_level(logging.WARNING, logger="App.Alerting"):
        settings = JsonAlertSettings(path)

    assert settings.heartbeat_hours() is None
    told = [r for r in caplog.records if "heartbeat interval" in r.getMessage()]
    assert len(told) == (0 if value is None else 1)


def test_a_read_only_copy_refuses_a_change(path: Path) -> None:
    settings = JsonAlertSettings(path, read_only=True)

    with pytest.raises(PermissionError):
        settings.set_heartbeat_hours(2)

    assert settings.heartbeat_hours() is None
    assert not path.exists()
