"""`EPIC-043D` — whether a price flashes on a tick is one shared, remembered setting, off by default."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.tick_flash_preference import (
    TickFlashPreference,
)


def test_the_flash_is_off_until_the_person_turns_it_on() -> None:
    assert TickFlashPreference().enabled is False


def test_a_change_tells_its_listeners_and_the_owner_once() -> None:
    told: list[bool] = []
    dirty: list[bool] = []
    preference = TickFlashPreference(on_changed=lambda: dirty.append(True))
    preference.subscribe(told.append)

    assert preference.set_enabled(True) is True

    assert preference.enabled is True
    assert told == [True]
    assert dirty == [True]


def test_choosing_what_is_already_chosen_changes_nothing() -> None:
    told: list[bool] = []
    preference = TickFlashPreference()
    preference.subscribe(told.append)

    assert preference.set_enabled(False) is False

    assert told == []


def test_a_listener_that_stopped_is_not_told() -> None:
    told: list[bool] = []
    preference = TickFlashPreference()
    stop = preference.subscribe(told.append)
    stop()

    preference.set_enabled(True)

    assert told == []


@pytest.mark.parametrize("enabled", [True, False])
def test_either_state_survives_a_save_and_a_restore(enabled: bool) -> None:
    first = TickFlashPreference()
    first.set_enabled(enabled)
    second = TickFlashPreference()

    second.restore_state(first.capture_state())

    assert second.enabled is enabled


@pytest.mark.parametrize("remembered", ["yes", 1, None, "true"])
def test_a_remembered_value_that_is_not_a_boolean_keeps_it_off_and_says_nothing(
    remembered: object,
) -> None:
    told: list[bool] = []
    preference = TickFlashPreference()
    preference.subscribe(told.append)

    preference.restore_state({"enabled": remembered})

    assert preference.enabled is False
    assert told == []
