"""`EPIC-043B` — the colour scheme the person chose is one shared, remembered setting."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.colour_scheme_preference import (
    ColourSchemeChoice,
    ColourSchemePreference,
)


def test_the_default_is_system() -> None:
    assert ColourSchemePreference().choice is ColourSchemeChoice.SYSTEM


def test_a_change_tells_its_listeners_and_the_owner_once() -> None:
    told: list[ColourSchemeChoice] = []
    dirty: list[bool] = []
    preference = ColourSchemePreference(on_changed=lambda: dirty.append(True))
    preference.subscribe(told.append)

    assert preference.set_choice(ColourSchemeChoice.DARK) is True

    assert preference.choice is ColourSchemeChoice.DARK
    assert told == [ColourSchemeChoice.DARK]
    assert dirty == [True]


def test_choosing_what_is_already_chosen_changes_nothing() -> None:
    told: list[ColourSchemeChoice] = []
    preference = ColourSchemePreference()
    preference.subscribe(told.append)

    assert preference.set_choice(ColourSchemeChoice.SYSTEM) is False

    assert told == []


def test_a_listener_that_stopped_is_not_told() -> None:
    told: list[ColourSchemeChoice] = []
    preference = ColourSchemePreference()
    stop = preference.subscribe(told.append)
    stop()

    preference.set_choice(ColourSchemeChoice.LIGHT)

    assert told == []


@pytest.mark.parametrize("choice", list(ColourSchemeChoice))
def test_every_choice_survives_a_save_and_a_restore(
    choice: ColourSchemeChoice,
) -> None:
    first = ColourSchemePreference()
    first.set_choice(choice)
    second = ColourSchemePreference()

    second.restore_state(first.capture_state())

    assert second.choice is choice


@pytest.mark.parametrize("remembered", ["sepia", None, 3, ""])
def test_a_remembered_value_this_build_does_not_know_degrades_to_system_quietly(
    remembered: object,
) -> None:
    told: list[ColourSchemeChoice] = []
    preference = ColourSchemePreference()
    preference.subscribe(told.append)
    preference.set_choice(ColourSchemeChoice.DARK)
    told.clear()

    preference.restore_state({"choice": remembered})

    assert preference.choice is ColourSchemeChoice.SYSTEM
    assert told == []
