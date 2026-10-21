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
    JsonAlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.settings_document import (
    SETTINGS_SCHEMA,
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


def test_setting_a_cell_again_replaces_it_and_none_puts_it_back_to_its_default(
    path: Path,
) -> None:
    settings = JsonAlertSettings(path)
    settings.set_route(AlertGroup.NOTICES, "discord", Loudness.LOUD)
    settings.set_route(AlertGroup.NOTICES, "discord", Loudness.SILENT)
    settings.set_route(AlertGroup.NOTICES, "telegram", Loudness.OFF)

    assert {(r.channel_id, r.loudness) for r in settings.routes()} == {
        ("discord", Loudness.SILENT),
        ("telegram", Loudness.OFF),
    }

    settings.set_route(AlertGroup.NOTICES, "telegram", None)
    settings.set_route(AlertGroup.NOTICES, "discord", None)

    assert settings.routes() == ()
    assert "routes" not in json.loads(path.read_text(encoding="utf-8"))
