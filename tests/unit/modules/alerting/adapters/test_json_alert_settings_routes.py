"""`EPIC-036D7` — the routing cells survive a restart and reach the hub; an entry this build does not know is its default again. Real files under `tmp_path`."""

from __future__ import annotations

import json
import logging
from datetime import time
from pathlib import Path

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
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_route import AlertRoute
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.bot_alert_mode import (
    BotAlertMode as Mode,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "state" / "alert_settings.json"


def _write(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def test_a_route_survives_a_restart_and_the_hub_sees_it(path: Path) -> None:
    """`EPIC-036D7`: a cell set to Off is Off for the next alert; every other cell is its default."""
    JsonAlertSettings(path).set_route(AlertGroup.ROUTINE, "discord", Loudness.OFF)

    again = JsonAlertSettings(path)

    assert again.routes() == (AlertRoute(AlertGroup.ROUTINE, "discord", Loudness.OFF),)
    hub = again.current()
    assert (
        hub.loudness_for(AlertGroup.ROUTINE, "discord", Severity.INFO) is Loudness.OFF
    )
    assert (
        hub.loudness_for(AlertGroup.ROUTINE, "telegram", Severity.INFO)
        is Loudness.SILENT
    )
    assert (
        hub.loudness_for(AlertGroup.BOT_EVENTS, "discord", Severity.CRITICAL)
        is Loudness.LOUD
    )


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


@pytest.mark.parametrize(
    "routes",
    [
        [{"group": "nope", "channel": "discord", "loudness": "off"}],
        [{"group": "routine", "channel": "discord", "loudness": "deafening"}],
        [{"group": "routine", "loudness": "off"}],
        ["routine"],
        "routine",
    ],
    ids=["bad-group", "bad-loudness", "missing-channel", "wrong-entry", "wrong-shape"],
)
def test_a_route_this_build_does_not_know_is_its_default_told_once_and_the_rest_kept(
    path: Path, routes: object, caplog: pytest.LogCaptureFixture
) -> None:
    """Default is the safe side: the cell is what N4 says, never a silence nobody chose."""
    _write(
        path,
        {
            "schema": SETTINGS_SCHEMA,
            "bot_modes": {"g3n092": "off"},
            "routes": routes,
        },
    )

    with caplog.at_level(logging.WARNING, logger="App.Alerting"):
        settings = JsonAlertSettings(path)

    assert settings.routes() == ()
    assert settings.current().mode_of("g3n092") is Mode.OFF
    assert len([r for r in caplog.records if "route" in r.getMessage()]) == 1


def test_one_good_route_beside_a_bad_one_is_kept(path: Path) -> None:
    _write(
        path,
        {
            "schema": SETTINGS_SCHEMA,
            "bot_modes": {},
            "routes": [
                {"group": "routine", "channel": "discord", "loudness": "off"},
                {"group": "nope", "channel": "discord", "loudness": "off"},
            ],
        },
    )

    assert JsonAlertSettings(path).routes() == (
        AlertRoute(AlertGroup.ROUTINE, "discord", Loudness.OFF),
    )


def test_a_read_only_copy_refuses_a_route_change(path: Path) -> None:
    settings = JsonAlertSettings(path, read_only=True)

    with pytest.raises(PermissionError):
        settings.set_route(AlertGroup.ROUTINE, "discord", Loudness.OFF)

    assert not path.exists()


def test_a_channel_that_is_not_text_is_not_turned_into_a_route(path: Path) -> None:
    """Review of PR #670: a hand-edited list must not become the channel "['x']"."""
    _write(
        path,
        {
            "schema": SETTINGS_SCHEMA,
            "bot_modes": {},
            "routes": [{"group": "routine", "channel": ["x"], "loudness": "off"}],
        },
    )

    assert JsonAlertSettings(path).routes() == ()


def test_a_cell_named_twice_is_its_default_not_the_last_word(
    path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The file says two things (`off` then `loud`, or the reverse): neither is trusted."""
    entry = {"group": "routine", "channel": "discord"}
    _write(
        path,
        {
            "schema": SETTINGS_SCHEMA,
            "bot_modes": {},
            "routes": [
                {**entry, "loudness": "off"},
                {**entry, "loudness": "loud"},
                {"group": "notices", "channel": "discord", "loudness": "silent"},
            ],
        },
    )

    with caplog.at_level(logging.WARNING, logger="App.Alerting"):
        settings = JsonAlertSettings(path)

    assert settings.routes() == (
        AlertRoute(AlertGroup.NOTICES, "discord", Loudness.SILENT),
    )
    assert len([r for r in caplog.records if "route" in r.getMessage()]) == 1
