"""`EPIC-036D8` — switching a channel on or off: only a channel this run has can be switched, a
store that cannot write is told, a read-only copy changes nothing. A real `JsonAlertSettings`
under `tmp_path`; nothing is doubled."""

from __future__ import annotations

from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.json_alert_settings import (
    JsonAlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.registered_channel_catalog import (
    RegisteredChannelCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.channels_setup import (
    ChannelsSetup,
    ChannelSwitch,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_channel import (
    FakeAlertChannel,
)


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "state" / "alert_settings.json"


def _setup(settings: JsonAlertSettings) -> ChannelsSetup:
    catalog = RegisteredChannelCatalog(
        {"discord": FakeAlertChannel(), "telegram": FakeAlertChannel()}
    )
    return ChannelsSetup(settings, catalog)


def test_the_state_lists_the_running_channels_and_the_ones_switched_off(
    path: Path,
) -> None:
    settings = JsonAlertSettings(path)
    setup = _setup(settings)
    setup.turn_off("telegram")

    state = setup.state()

    assert state.channels == ("discord", "telegram")
    assert state.disabled == {"telegram"}
    assert state.editable


def test_a_channel_is_switched_off_and_on_again(path: Path) -> None:
    settings = JsonAlertSettings(path)
    setup = _setup(settings)

    assert setup.turn_off("discord") is ChannelSwitch.TURNED_OFF
    assert settings.current().disabled_channels == {"discord"}
    assert setup.turn_on("discord") is ChannelSwitch.TURNED_ON
    assert settings.current().disabled_channels == frozenset()


def test_a_channel_this_run_does_not_have_is_refused_and_nothing_is_kept(
    path: Path,
) -> None:
    settings = JsonAlertSettings(path)

    outcome = _setup(settings).turn_off("signal")

    assert outcome is ChannelSwitch.UNKNOWN_CHANNEL
    assert settings.disabled() == frozenset()
    assert not path.exists()


def test_a_read_only_copy_changes_nothing_and_says_so(path: Path) -> None:
    settings = JsonAlertSettings(path, read_only=True)
    setup = _setup(settings)

    assert setup.turn_off("discord") is ChannelSwitch.READ_ONLY
    assert not setup.state().editable
    assert not path.exists()


def test_a_store_that_cannot_write_is_told_not_reported_switched(path: Path) -> None:
    settings = JsonAlertSettings(path)
    path.parent.mkdir(parents=True)
    path.mkdir()  # the file's place is a folder: the write raises OSError

    outcome = _setup(settings).turn_off("discord")

    assert outcome is ChannelSwitch.NOT_KEPT
    assert settings.disabled() == frozenset()
