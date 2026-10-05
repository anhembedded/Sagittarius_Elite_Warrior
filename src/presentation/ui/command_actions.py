"""A contributed command, as the Engine's action (`EPIC-033D`).

`CommandContribution` is the app's plain declaration (`core/contracts` may
not name the Engine). `ActionDescriptor` is the Engine's, and it validates the
text, the menu path and the shortcut: an invalid command fails the window's
build with the command's id in the message.
"""

from __future__ import annotations

from PySide6.QtGui import QKeySequence
from Sagittarius_Elite_Warrior.src.core.contracts.command_contribution import (
    CommandContribution,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.action_descriptor import (
    ActionConfirmation,
    ActionDescriptor,
)

#: The toolbar every mode's commands go on (`ModeHost`'s commands toolbar).
COMMANDS_TOOLBAR = "commands"


def action_descriptor(command: CommandContribution) -> ActionDescriptor:
    confirm = command.confirm
    shortcut: str | QKeySequence.StandardKey | None = command.shortcut
    if command.standard_shortcut is not None:
        # An unknown name raises AttributeError naming it, at build time.
        shortcut = getattr(QKeySequence.StandardKey, command.standard_shortcut)
    return ActionDescriptor(
        action_id=command.command_id,
        text=command.text,
        menu_path=command.menu_path,
        toolbar=COMMANDS_TOOLBAR if command.on_toolbar else None,
        shortcut=shortcut,
        checkable=command.checkable,
        needs_input=command.needs_input,
        confirm=(
            ActionConfirmation(
                title=confirm.title,
                consequence=confirm.consequence,
                accept_text=confirm.accept_text,
            )
            if confirm is not None
            else None
        ),
        surface_id=command.mode,
    )
