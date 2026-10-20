"""`EPIC-043B` — Tools → Options → Appearance: the colour scheme choice, applied with OK or Apply."""

from __future__ import annotations

from PySide6.QtWidgets import QRadioButton
from Sagittarius_Elite_Warrior.src.core.contracts.i_options_section import (
    IOptionsSection,
)
from Sagittarius_Elite_Warrior.src.shell.appearance_options.appearance_options_page import (
    AppearanceOptionsPage,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.colour_scheme_preference import (
    ColourSchemeChoice,
    ColourSchemePreference,
)


def _radio(page: AppearanceOptionsPage, choice: ColourSchemeChoice) -> QRadioButton:
    button = page.widget().findChild(
        QRadioButton, f"options::appearance::{choice.value}"
    )
    assert button is not None
    return button


def test_the_page_satisfies_the_dialogs_contract(qapp) -> None:
    assert isinstance(AppearanceOptionsPage(ColourSchemePreference()), IOptionsSection)


def test_the_page_opens_on_the_saved_choice_and_is_clean(qapp) -> None:
    preference = ColourSchemePreference()
    preference.restore_state({"choice": "dark"})

    page = AppearanceOptionsPage(preference)

    assert _radio(page, ColourSchemeChoice.DARK).isChecked()
    assert not page.is_dirty()


def test_clicking_a_choice_is_dirty_and_changes_nothing_until_apply(qapp) -> None:
    preference = ColourSchemePreference()
    page = AppearanceOptionsPage(preference)
    told: list[bool] = []
    page.set_change_listener(lambda: told.append(True))

    _radio(page, ColourSchemeChoice.LIGHT).click()

    assert page.is_dirty()
    assert told == [True]
    assert preference.choice is ColourSchemeChoice.SYSTEM


def test_apply_writes_the_choice_and_the_page_is_clean_again(qapp) -> None:
    preference = ColourSchemePreference()
    page = AppearanceOptionsPage(preference)
    _radio(page, ColourSchemeChoice.DARK).click()

    page.apply()

    assert preference.choice is ColourSchemeChoice.DARK
    assert not page.is_dirty()


def test_revert_puts_the_saved_choice_back(qapp) -> None:
    preference = ColourSchemePreference()
    page = AppearanceOptionsPage(preference)
    _radio(page, ColourSchemeChoice.DARK).click()

    page.revert()

    assert _radio(page, ColourSchemeChoice.SYSTEM).isChecked()
    assert not page.is_dirty()


def test_exactly_one_choice_is_checked_at_a_time(qapp) -> None:
    page = AppearanceOptionsPage(ColourSchemePreference())

    _radio(page, ColourSchemeChoice.LIGHT).click()
    _radio(page, ColourSchemeChoice.DARK).click()

    checked = [c for c in ColourSchemeChoice if _radio(page, c).isChecked()]
    assert checked == [ColourSchemeChoice.DARK]
