"""`EPIC-036D7` — choosing a cell of the routing matrix: only a channel this run has can be set, a
cell put back is no route (not a copy of the default), and a store that cannot write is told.
A real `JsonAlertSettings` under `tmp_path`; nothing is doubled."""

from __future__ import annotations

from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.json_alert_settings import (
    JsonAlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.registered_channel_catalog import (
    RegisteredChannelCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.routing_setup import (
    RouteSave,
    RoutingSetup,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_channel import (
    FakeAlertChannel,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_group import AlertGroup
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "state" / "alert_settings.json"


def _setup(settings: JsonAlertSettings) -> RoutingSetup:
    catalog = RegisteredChannelCatalog(
        {"discord": FakeAlertChannel(), "telegram": FakeAlertChannel()}
    )
    return RoutingSetup(settings, catalog)


def test_the_state_lists_the_running_channels_and_what_the_owner_chose(
    path: Path,
) -> None:
    settings = JsonAlertSettings(path)
    setup = _setup(settings)
    setup.set_cell(AlertGroup.ROUTINE, "discord", Loudness.OFF)

    state = setup.state()

    assert state.channels == ("discord", "telegram")
    assert state.chosen == {(AlertGroup.ROUTINE, "discord"): Loudness.OFF}
    assert state.editable


def test_a_cell_is_kept_and_reaches_the_hub(path: Path) -> None:
    settings = JsonAlertSettings(path)

    outcome = _setup(settings).set_cell(AlertGroup.NOTICES, "telegram", Loudness.LOUD)

    assert outcome is RouteSave.SAVED
    hub = settings.current()
    assert (
        hub.loudness_for(AlertGroup.NOTICES, "telegram", Severity.WARNING)
        is Loudness.LOUD
    )
    assert (
        hub.loudness_for(AlertGroup.NOTICES, "discord", Severity.WARNING)
        is Loudness.SILENT
    )
    assert len(settings.routes()) == 1


def test_a_cell_put_back_is_no_route_at_all(path: Path) -> None:
    settings = JsonAlertSettings(path)
    setup = _setup(settings)
    setup.set_cell(AlertGroup.NOTICES, "telegram", Loudness.LOUD)

    outcome = setup.set_cell(AlertGroup.NOTICES, "telegram", None)

    assert outcome is RouteSave.BACK_TO_DEFAULT
    assert settings.routes() == ()


def test_a_channel_this_run_does_not_have_is_refused_and_nothing_is_kept(
    path: Path,
) -> None:
    settings = JsonAlertSettings(path)

    outcome = _setup(settings).set_cell(AlertGroup.ROUTINE, "signal", Loudness.OFF)

    assert outcome is RouteSave.UNKNOWN_CHANNEL
    assert settings.routes() == ()
    assert not path.exists()


def test_a_read_only_copy_changes_nothing_and_says_so(path: Path) -> None:
    settings = JsonAlertSettings(path, read_only=True)
    setup = _setup(settings)

    assert (
        setup.set_cell(AlertGroup.ROUTINE, "discord", Loudness.OFF)
        is RouteSave.READ_ONLY
    )
    assert not setup.state().editable
    assert not path.exists()


def test_a_store_that_cannot_write_is_told_not_reported_saved(path: Path) -> None:
    settings = JsonAlertSettings(path)
    path.parent.mkdir(parents=True)
    path.mkdir()  # the file's place is a folder: the write raises OSError

    outcome = _setup(settings).set_cell(AlertGroup.ROUTINE, "discord", Loudness.OFF)

    assert outcome is RouteSave.NOT_KEPT
    assert settings.routes() == ()
