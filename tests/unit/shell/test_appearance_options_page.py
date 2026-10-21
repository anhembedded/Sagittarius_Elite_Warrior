"""`EPIC-043B` — Tools → Options → Appearance: the colour scheme choice, applied with OK or Apply."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QRadioButton
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
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.tick_flash_preference import (
    TickFlashPreference,
)


def _radio(page: AppearanceOptionsPage, choice: ColourSchemeChoice) -> QRadioButton:
    button = page.widget().findChild(
        QRadioButton, f"options::appearance::{choice.value}"
    )
    assert button is not None
    return button


def test_the_page_satisfies_the_dialogs_contract(qapp) -> None:
    assert isinstance(
        AppearanceOptionsPage(ColourSchemePreference(), TickFlashPreference()),
        IOptionsSection,
    )


def test_the_page_opens_on_the_saved_choice_and_is_clean(qapp) -> None:
    preference = ColourSchemePreference()
    preference.restore_state({"choice": "dark"})

    page = AppearanceOptionsPage(preference, TickFlashPreference())

    assert _radio(page, ColourSchemeChoice.DARK).isChecked()
    assert not page.is_dirty()


def test_clicking_a_choice_is_dirty_and_changes_nothing_until_apply(qapp) -> None:
    preference = ColourSchemePreference()
    page = AppearanceOptionsPage(preference, TickFlashPreference())
    told: list[bool] = []
    page.set_change_listener(lambda: told.append(True))

    _radio(page, ColourSchemeChoice.LIGHT).click()

    assert page.is_dirty()
    assert told == [True]
    assert preference.choice is ColourSchemeChoice.SYSTEM


def test_apply_writes_the_choice_and_the_page_is_clean_again(qapp) -> None:
    preference = ColourSchemePreference()
    page = AppearanceOptionsPage(preference, TickFlashPreference())
    _radio(page, ColourSchemeChoice.DARK).click()

    page.apply()

    assert preference.choice is ColourSchemeChoice.DARK
    assert not page.is_dirty()


def test_revert_puts_the_saved_choice_back(qapp) -> None:
    preference = ColourSchemePreference()
    page = AppearanceOptionsPage(preference, TickFlashPreference())
    _radio(page, ColourSchemeChoice.DARK).click()

    page.revert()

    assert _radio(page, ColourSchemeChoice.SYSTEM).isChecked()
    assert not page.is_dirty()


def test_exactly_one_choice_is_checked_at_a_time(qapp) -> None:
    page = AppearanceOptionsPage(ColourSchemePreference(), TickFlashPreference())

    _radio(page, ColourSchemeChoice.LIGHT).click()
    _radio(page, ColourSchemeChoice.DARK).click()

    checked = [c for c in ColourSchemeChoice if _radio(page, c).isChecked()]
    assert checked == [ColourSchemeChoice.DARK]


# -- `EPIC-043D`: the tick flash ----------------------------------------------------------


def _flash_box(page: AppearanceOptionsPage) -> QCheckBox:
    box = page.widget().findChild(QCheckBox, "options::appearance::tick_flash")
    assert box is not None
    return box


def test_the_flash_is_unchecked_and_the_page_clean_on_the_default(qapp) -> None:
    page = AppearanceOptionsPage(ColourSchemePreference(), TickFlashPreference())

    assert not _flash_box(page).isChecked()
    assert not page.is_dirty()


def test_the_page_opens_on_a_flash_that_is_saved_on(qapp) -> None:
    flash = TickFlashPreference()
    flash.restore_state({"enabled": True})

    page = AppearanceOptionsPage(ColourSchemePreference(), flash)

    assert _flash_box(page).isChecked()
    assert not page.is_dirty()


def test_ticking_the_flash_is_dirty_and_changes_nothing_until_apply(qapp) -> None:
    flash = TickFlashPreference()
    page = AppearanceOptionsPage(ColourSchemePreference(), flash)
    told: list[bool] = []
    page.set_change_listener(lambda: told.append(True))

    _flash_box(page).click()

    assert page.is_dirty()
    assert told == [True]
    assert flash.enabled is False


def test_apply_turns_the_flash_on_and_off_and_the_page_is_clean_after_each(
    qapp,
) -> None:
    flash = TickFlashPreference()
    page = AppearanceOptionsPage(ColourSchemePreference(), flash)

    _flash_box(page).click()
    page.apply()
    assert flash.enabled is True
    assert not page.is_dirty()

    _flash_box(page).click()
    page.apply()
    assert flash.enabled is False
    assert not page.is_dirty()


def test_revert_puts_the_saved_flash_back(qapp) -> None:
    flash = TickFlashPreference()
    page = AppearanceOptionsPage(ColourSchemePreference(), flash)
    _flash_box(page).click()

    page.revert()

    assert not _flash_box(page).isChecked()
    assert not page.is_dirty()


def test_apply_changes_the_colour_scheme_without_touching_the_flash_and_the_reverse(
    qapp,
) -> None:
    scheme, flash = ColourSchemePreference(), TickFlashPreference()
    page = AppearanceOptionsPage(scheme, flash)

    _radio(page, ColourSchemeChoice.DARK).click()
    page.apply()

    assert scheme.choice is ColourSchemeChoice.DARK
    assert flash.enabled is False
