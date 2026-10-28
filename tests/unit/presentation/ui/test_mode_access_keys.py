"""`BOT-210` — a mode's access key in View is declared, so adding a mode cannot move another mode's
key onto a View command's.

The window used to give each title the first free letter in mode order. Adding `Alerts` before
`Backtest engine` moved Backtest from `a` to `c`, onto `Remove from Wat&chlist`, and every
conformance case failed at boot; the fix then moved that one command. Now each mode names its letter
(`NavMetadata.access_key`): the first group of tests is the helper's rules, the second holds the real
modes and the real View commands to them, as a property over what is contributed, so a mode or a
command added tomorrow with a letter already taken fails here, naming both."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.nav_metadata import NavMetadata
from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import _VIEW_MENU_KEYS
from Sagittarius_Elite_Warrior.src.presentation.ui.mode_access_keys import (
    ModeAccessKeyError,
    mode_labels,
)
from Sagittarius_Elite_Warrior.tests.conftest import real_contributions
from sagittarius_engine.extensions.pyside_mvc.workbench.action_text import access_keys

_VIEW = "&View"


def _nav(title: str, key: str = "") -> NavMetadata:
    return NavMetadata(title=title, icon="x", access_key=key)


def test_a_declared_key_marks_its_letter_in_the_title() -> None:
    labels = mode_labels([_nav("Backtest engine", "c"), _nav("Alerts", "a")], ["o"])

    assert labels == ["Ba&cktest engine", "&Alerts"]


def test_adding_a_mode_moves_no_other_modes_key() -> None:
    before = mode_labels([_nav("Bots", "b"), _nav("Backtest engine", "c")], ["o", "u"])

    after = mode_labels(
        [_nav("Alerts", "a"), _nav("Bots", "b"), _nav("Backtest engine", "c")],
        ["o", "u"],
    )

    assert after[1:] == before
    assert after[0] == "&Alerts"


def test_a_letter_that_is_not_in_the_title_is_refused_by_name() -> None:
    with pytest.raises(ModeAccessKeyError, match="'Alerts'.*'z'"):
        mode_labels([_nav("Alerts", "z")], [])


def test_a_character_that_is_not_a_letter_is_refused() -> None:
    with pytest.raises(ModeAccessKeyError, match="'Backtest engine'"):
        mode_labels([_nav("Backtest engine", " ")], [])


def test_more_than_one_letter_is_refused() -> None:
    with pytest.raises(ModeAccessKeyError, match="'Alerts'"):
        mode_labels([_nav("Alerts", "al")], [])


def test_two_modes_declaring_one_letter_are_refused_naming_both() -> None:
    with pytest.raises(ModeAccessKeyError, match="'Bots' and 'Backtest engine'"):
        mode_labels([_nav("Bots", "b"), _nav("Backtest engine", "b")], [])


def test_a_letter_a_view_item_holds_is_refused() -> None:
    with pytest.raises(ModeAccessKeyError, match="'Tools'.*'o'"):
        mode_labels([_nav("Tools", "o")], ["o", "u"])


def test_a_key_is_case_insensitive() -> None:
    assert mode_labels([_nav("Alerts", "A")], []) == ["&Alerts"]


def test_a_mode_with_no_declared_key_takes_a_letter_nobody_holds() -> None:
    labels = mode_labels([_nav("Bots", "b"), _nav("Backtest engine")], ["o"])

    assert labels[0] == "&Bots"
    assert access_keys(labels[1]) and access_keys(labels[1])[0] not in {"b", "o"}


# -- the real modes and the real View commands ---------------------------------


@pytest.fixture(scope="module")
def contributions():
    return real_contributions(Mock(), dev_mode=True)


def _real_navs(contributions) -> list[NavMetadata]:
    return [
        screen.nav
        for screen in contributions.screens()
        if screen.nav is not None and screen.nav.is_navigable
    ]


def test_every_real_mode_declares_its_access_key(contributions) -> None:
    undeclared = [nav.title for nav in _real_navs(contributions) if not nav.access_key]

    assert undeclared == [], f"declare `access_key` in the NavMetadata of: {undeclared}"


def test_the_real_modes_keys_are_none_of_a_view_commands(contributions) -> None:
    """The modes' View items sit beside every mode's own View commands and the submenus they
    open (`C&hart`): a letter one holds is one the others cannot. Any mode may be in front, so
    the check is against all of them."""
    navs = _real_navs(contributions)
    mode_keys = {
        key: nav.title
        for nav, label in zip(navs, mode_labels(navs, _VIEW_MENU_KEYS), strict=True)
        for key in access_keys(label)
    }
    command_keys: dict[str, list[str]] = {}
    for command in contributions.commands():
        if command.menu_path[:1] != (_VIEW,):
            continue
        # A View item, or the submenu its path opens under View.
        text = command.text if len(command.menu_path) == 1 else command.menu_path[1]
        for key in access_keys(text):
            command_keys.setdefault(key, []).append(text)

    clashes = {
        f"{mode_keys[key]} and {command_keys[key]} on '{key}'"
        for key in mode_keys.keys() & command_keys.keys()
    }

    assert not clashes, "\n".join(sorted(clashes))


@pytest.mark.parametrize("dev_mode", [True, False], ids=["developer", "normal"])
def test_the_real_modes_show_the_same_keys_with_or_without_developer_mode(
    dev_mode: bool,
) -> None:
    """The keys the window shows, pinned for both runs. In developer mode they are the ones the
    window assigned before the keys were declared; in a normal run Backtest engine was `&engine`
    (no Developer mode took `e` away from it) and is now `Ba&cktest engine`: one key in both runs
    is the stability the declaration is for, and the one key a normal user sees move."""
    navs = _real_navs(real_contributions(Mock(), dev_mode=dev_mode))

    labels = dict(
        zip(
            (nav.title for nav in navs),
            mode_labels(navs, _VIEW_MENU_KEYS),
            strict=True,
        )
    )

    expected = {
        "Market": "&Market",
        "Trade": "&Trade",
        "Bots": "&Bots",
        "Data": "&Data",
        "Alerts": "&Alerts",
        "Backtest engine": "Ba&cktest engine",
        # `EPIC-047E`: declared `v`, taken by no other mode or View command.
        "VPS Bots": "&VPS Bots",
    }
    if dev_mode:
        expected["Developer"] = "D&eveloper"
    assert labels == expected
