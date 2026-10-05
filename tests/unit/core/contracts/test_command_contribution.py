"""`EPIC-033D` — a command has one key: its own, or a platform command's;
`EPIC-033Q` — checkable commands of one exclusive group are one choice."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject
from PySide6.QtGui import QAction, QKeySequence
from Sagittarius_Elite_Warrior.src.core.contracts.command_contribution import (
    CommandContribution,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.command_actions import (
    action_descriptor,
    exclusive_groups,
)


def _command(**keys: str) -> CommandContribution:
    return CommandContribution(
        contributor_id="bots",
        command_id="bots.save",
        text="&Save bot",
        menu_path=("&Bots",),
        **keys,
    )


def test_a_standard_shortcut_resolves_to_the_platform_key() -> None:
    descriptor = action_descriptor(_command(standard_shortcut="Save"))

    assert descriptor.shortcut is QKeySequence.StandardKey.Save


def test_a_command_with_both_kinds_of_shortcut_is_refused() -> None:
    with pytest.raises(ValueError, match="bots.save"):
        _command(shortcut="Ctrl+S", standard_shortcut="Save")


def test_an_exclusive_group_on_a_command_that_is_not_checkable_is_refused() -> None:
    with pytest.raises(ValueError, match="bots.save"):
        _command(exclusive_group="bots.choice")


def test_commands_of_one_exclusive_group_check_one_at_a_time(qapp) -> None:
    """`EPIC-033Q`: checking one unchecks the others; checking the checked
    one keeps it, so the choice never reads "none"."""
    owner = QObject()
    built = []
    for name in ("one", "two"):
        command = CommandContribution(
            contributor_id="bots",
            command_id=f"bots.{name}",
            text=f"&{name}",
            menu_path=("&Bots",),
            checkable=True,
            exclusive_group="bots.choice",
        )
        action = QAction(command.text, owner)
        action.setCheckable(True)
        built.append((command, action))
    plain = QAction("&Plain", owner)
    built.append((_command(), plain))

    groups = exclusive_groups(built, owner)
    one, two = built[0][1], built[1][1]
    one.trigger()
    two.trigger()
    two.trigger()

    assert list(groups) == ["bots.choice"]
    assert groups["bots.choice"].actions() == [one, two]
    assert (one.isChecked(), two.isChecked()) == (False, True)
    assert plain.actionGroup() is None
