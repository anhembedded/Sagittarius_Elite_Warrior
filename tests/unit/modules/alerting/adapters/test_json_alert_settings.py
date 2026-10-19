"""`BOT-191` — what the owner set per bot survives a restart, and a file that is missing,
older, newer or damaged never stops the app or silences a bot.

Real files under `tmp_path`; nothing is doubled.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.json_alert_settings import (
    SETTINGS_SCHEMA,
    JsonAlertSettings,
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


def test_a_read_only_copy_keeps_the_change_in_memory_and_writes_nothing(
    path: Path,
) -> None:
    settings = JsonAlertSettings(path, read_only=True)

    settings.set_mode("g3n092", Mode.OFF)

    assert settings.current().mode_of("g3n092") is Mode.OFF
    assert not path.exists()


def test_a_write_that_fails_changes_nothing_in_memory(path: Path) -> None:
    path.parent.parent.mkdir(parents=True, exist_ok=True)
    path.parent.write_text("a file where the state folder goes", encoding="utf-8")
    settings = JsonAlertSettings(path)

    with pytest.raises(OSError):
        settings.set_mode("g3n092", Mode.OFF)

    assert settings.current().mode_of("g3n092") is Mode.ON
