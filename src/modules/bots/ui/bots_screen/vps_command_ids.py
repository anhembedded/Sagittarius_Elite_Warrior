"""`EPIC-047E` - the VPS Bots tab's commands: the Bots tab's own, under ids of their own.

@details A command id is unique in the window, and the Bots screen binds the ids of `bots_commands.py`. The VPS tab is the
same screen, so it contributes the same commands under the prefix `bots.vps` (`vps_commands`) and binds them through
`PrefixedBinder`, which turns each `bots.bots...` id the screen asks for into the tab's own. No Bots command file knows a
second tab exists (the screen reaches the tab only through `BotsBackend`; `backend_for` chooses the VPS one because the shell
builds the presenter through a `Deferred` that passes only a container).

Qt-free for `vps_commands` (the shell contributes it on a headless run); `PrefixedBinder` only forwards.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)

from .bots_commands import COMMAND_PREFIX, bots_commands

if TYPE_CHECKING:
    from PySide6.QtCore import SignalInstance
    from PySide6.QtGui import QAction
    from Sagittarius_Elite_Warrior.src.core.contracts.command_contribution import (
        CommandContribution,
    )

VPS_COMMAND_PREFIX = "bots.vps"


def vps_command_id(bots_command_id: str) -> str:
    """The VPS tab's id for a Bots tab command id."""
    return VPS_COMMAND_PREFIX + bots_command_id.removeprefix(COMMAND_PREFIX)


def vps_commands(route: str) -> tuple[CommandContribution, ...]:
    """The Bots tab's commands at `route`, under the VPS tab's ids."""
    return tuple(
        replace(command, command_id=vps_command_id(command.command_id))
        for command in bots_commands(route)
    )


class PrefixedBinder(ICommandBinder):
    """An `ICommandBinder` that binds the VPS tab's id for every Bots tab id it is asked for."""

    def __init__(self, inner: ICommandBinder) -> None:
        self._inner = inner

    def bind(
        self,
        action_id: str,
        handler: Callable[[bool], None],
        *,
        enabled: SignalInstance | None = None,
        checked: SignalInstance | None = None,
        initially_enabled: bool = True,
    ) -> None:
        self._inner.bind(
            vps_command_id(action_id),
            handler,
            enabled=enabled,
            checked=checked,
            initially_enabled=initially_enabled,
        )

    def action(self, action_id: str) -> QAction:
        return self._inner.action(vps_command_id(action_id))
