"""`EPIC-036D8` — a channel switched off survives a restart and reaches the hub and the router; an
entry this build does not know leaves its channel on. Real files under `tmp_path`."""

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
from Sagittarius_Elite_Warrior.src.modules.alerting.application.alert_router import (
    AlertRouter,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_group import AlertGroup
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_route import AlertRoute
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import an_alert


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "state" / "alert_settings.json"


def _write(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def test_a_channel_switched_off_survives_a_restart_and_the_hub_sees_it(
    path: Path,
) -> None:
    JsonAlertSettings(path).disable("telegram")

    again = JsonAlertSettings(path)

    assert again.disabled() == {"telegram"}
    assert again.current().disabled_channels == {"telegram"}


def test_switching_a_channel_on_again_removes_it_from_the_file(path: Path) -> None:
    settings = JsonAlertSettings(path)
    settings.disable("telegram")
    settings.disable("discord")

    settings.enable("telegram")

    assert JsonAlertSettings(path).disabled() == {"discord"}
    settings.enable("discord")
    assert "disabled_channels" not in json.loads(path.read_text(encoding="utf-8"))


def test_the_router_never_sends_to_a_switched_off_channel_not_even_for_a_critical(
    path: Path,
) -> None:
    settings = JsonAlertSettings(path)
    settings.disable("telegram")

    targets = AlertRouter().route(
        an_alert(AlertKind.BOT_HALTED), settings.current(), ("discord", "telegram")
    )

    assert [target.channel_id for target in targets] == ["discord"]


def test_switching_a_channel_off_keeps_the_routes_and_modes_beside_it(
    path: Path,
) -> None:
    settings = JsonAlertSettings(path)
    settings.set_route(AlertGroup.ROUTINE, "discord", Loudness.OFF)

    settings.disable("telegram")

    again = JsonAlertSettings(path)
    assert again.routes() == (AlertRoute(AlertGroup.ROUTINE, "discord", Loudness.OFF),)
    assert again.disabled() == {"telegram"}


def test_an_entry_that_is_not_text_is_skipped_told_once_and_the_rest_kept(
    path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _write(
        path,
        {
            "schema": SETTINGS_SCHEMA,
            "bot_modes": {},
            "disabled_channels": ["telegram", 7, None],
        },
    )

    with caplog.at_level(logging.WARNING, logger="App.Alerting"):
        settings = JsonAlertSettings(path)

    assert settings.disabled() == {"telegram"}
    warnings = [r for r in caplog.records if "disabled channel" in r.getMessage()]
    assert len(warnings) == 1


def test_a_disabled_list_that_is_not_a_list_leaves_every_channel_on(
    path: Path,
) -> None:
    _write(
        path,
        {"schema": SETTINGS_SCHEMA, "bot_modes": {}, "disabled_channels": "telegram"},
    )

    assert JsonAlertSettings(path).disabled() == frozenset()


def test_a_read_only_copy_refuses_a_switch(path: Path) -> None:
    settings = JsonAlertSettings(path, read_only=True)

    with pytest.raises(PermissionError):
        settings.disable("telegram")

    assert settings.disabled() == frozenset()
    assert not path.exists()
