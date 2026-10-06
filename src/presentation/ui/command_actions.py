"""A contributed command, as the Engine's action (`EPIC-033D`).

`CommandContribution` is the app's plain declaration (`core/contracts` may
not name the Engine). `ActionDescriptor` is the Engine's, and it validates the
text, the menu path and the shortcut: an invalid command fails the window's
build with the command's id in the message.
"""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction, QActionGroup, QColor, QKeySequence
from Sagittarius_Elite_Warrior.src.core.contracts.command_contribution import (
    CommandContribution,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.assets.icon_loader import (
    get_icon_loader,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.action_descriptor import (
    ActionConfirmation,
    ActionDescriptor,
)

#: The toolbar every mode's commands go on (`ModeHost`'s commands toolbar).
COMMANDS_TOOLBAR = "commands"
#: The icon's source size in pixels; Qt scales it down to the toolbar's icon
#: size, so it stays sharp.
_COMMAND_ICON_SIZE = 24


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
        group=command.group,
    )


def exclusive_groups(
    commands: Iterable[tuple[CommandContribution, QAction]], owner: QObject
) -> dict[str, QActionGroup]:
    """One exclusive `QActionGroup` per `exclusive_group` the commands name,
    holding each command's action, by group name."""
    groups: dict[str, QActionGroup] = {}
    for command, action in commands:
        name = command.exclusive_group
        if name is None:
            continue
        group = groups.get(name)
        if group is None:
            group = QActionGroup(owner)
            group.setObjectName(f"actionGroup::{name}")
            group.setExclusionPolicy(QActionGroup.ExclusionPolicy.Exclusive)
            groups[name] = group
        group.addAction(action)
    return groups


def apply_icons(
    commands: Iterable[tuple[CommandContribution, QAction]], colour: QColor
) -> None:
    """Sets the icon each command names on its action (`BOT-164`), drawn in
    `colour`, the palette's text colour, so the platform's theme decides it."""
    for command, action in commands:
        if command.icon is not None:
            action.setIcon(
                get_icon_loader().get_icon(
                    command.icon, colour.name(), _COMMAND_ICON_SIZE
                )
            )
