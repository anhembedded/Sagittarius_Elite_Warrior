"""`EPIC-033D` — a command has one key: its own, or a platform command's."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QKeySequence
from Sagittarius_Elite_Warrior.src.core.contracts.command_contribution import (
    CommandContribution,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.command_actions import (
    action_descriptor,
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
