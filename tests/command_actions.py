"""`EPIC-033D` — contributed commands as the window builds them, for tests.

`bound_actions` builds the Engine's real `ActionRegistry` from the commands a
module contributes, through the window's own `action_descriptor`, and lets
what performs them bind, as `MainWindow` calls `bind_commands`, with the
window's exclusive groups made first, as `MainWindow` makes them. Only the
confirmation dialog is replaced, by `RecordingConfirmer`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.command_contribution import (
    CommandContribution,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.command_actions import (
    action_descriptor,
    exclusive_groups,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.action_descriptor import (
    ActionConfirmation,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.action_registry import (
    ActionRegistry,
)


@dataclass
class RecordingConfirmer:
    """An `IActionConfirmer` that answers `answer` and keeps every question."""

    answer: bool = True
    asked: list[ActionConfirmation] = field(default_factory=list)

    def confirm(self, parent: QWidget | None, confirmation: ActionConfirmation) -> bool:
        self.asked.append(confirmation)
        return self.answer


def bound_actions(
    owner: QObject,
    commands: Iterable[CommandContribution],
    bind: Callable[[ICommandBinder], None],
    confirmer: RecordingConfirmer | None = None,
) -> ActionRegistry:
    """`commands` as actions owned by `owner`, bound by `bind`."""
    registry = ActionRegistry(owner, confirmer or RecordingConfirmer())
    built = [
        (command, registry.contribute(action_descriptor(command)))
        for command in commands
    ]
    exclusive_groups(built, owner)
    bind(registry)
    return registry
