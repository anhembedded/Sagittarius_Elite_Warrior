"""Keeps a mode's commands in step with actions another widget owns
(`BOT-156`, `EPIC-033K`).

The commands are the shell's actions, in a menu; the actions they mirror
belong to a toolbar inside a panel or a chart, which the person may also
click. A command drives its action, and the action says back whether it is
enabled and, when checkable, checked. With nothing followed every command is
off. A mode follows new actions whenever their owner changes (the chart in
front, the selected bot's kind); the previous ones' connections are dropped,
so a closed owner's actions drive nothing, whatever order it is deleted in.

Presenter-owned (`async-ui-action-rule.md` §2), never registered. Each use is
a subclass that names its commands: `ChartCommandMirror` (a chart's zoom and
timeframe actions), `KindCommands` (a bot kind's toolbar).
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import partial

from PySide6.QtCore import QMetaObject, QObject, Signal
from PySide6.QtGui import QAction
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)


class _CommandState(QObject):
    """One command's shown state, and the receiver of its followed action's
    `destroyed`: a child of the mirror, so Qt drops that connection when the
    mirror goes first (review of PR #372)."""

    checked = Signal(bool)
    enabled = Signal(bool)
    #: The followed action went with its owner; carries the command's key.
    actionGone = Signal(str)

    def __init__(self, key: str, parent: QObject) -> None:
        super().__init__(parent)
        self._key = key

    def on_action_destroyed(self, _gone: QObject | None = None) -> None:
        self.actionGone.emit(self._key)


class ActionMirror(QObject):
    """@brief Commands, by key, driving and following one owner's actions."""

    def __init__(
        self, command_ids: Mapping[str, str], parent: QObject | None = None
    ) -> None:
        """`command_ids` maps each key `follow()` is handed to the id of the
        command that mirrors its action."""
        super().__init__(parent)
        self._command_ids = dict(command_ids)
        self._states = {key: _CommandState(key, self) for key in self._command_ids}
        for state in self._states.values():
            state.actionGone.connect(self._forget)
        self._actions: dict[str, QAction] = {}
        self._connections: list[QMetaObject.Connection] = []

    def bind_commands(self, binder: ICommandBinder) -> None:
        for key, state in self._states.items():
            binder.bind(
                self._command_ids[key],
                partial(self._on_command, key),
                enabled=state.enabled,
                checked=state.checked,
                initially_enabled=False,
            )

    def follow(self, actions: Mapping[str, QAction] | None) -> None:
        """Follows `actions`, by key; `None` means nothing to follow, and
        every command off."""
        if actions is not None and actions == self._actions:
            return
        for connection in self._connections:
            QObject.disconnect(connection)
        self._connections = []
        self._actions = dict(actions) if actions is not None else {}
        for key, state in self._states.items():
            action = self._actions.get(key)
            if action is None:
                state.enabled.emit(False)
                continue
            self._connections.append(action.enabledChanged.connect(state.enabled.emit))
            self._connections.append(action.toggled.connect(state.checked.emit))
            self._connections.append(
                action.destroyed.connect(state.on_action_destroyed)
            )
            state.enabled.emit(action.isEnabled())
            state.checked.emit(action.isChecked())

    def _forget(self, key: str) -> None:
        """A followed action went with its owner before the mode followed
        another: its command drives nothing and is off, whatever order the
        host closes and re-follows in."""
        if self._actions.pop(key, None) is not None:
            self._states[key].enabled.emit(False)

    def _on_command(self, key: str, checked: bool) -> None:
        action = self._actions.get(key)
        if action is None or not action.isEnabled():
            return
        if action.isCheckable():
            if action.isChecked() != checked:
                action.setChecked(checked)
        else:
            action.trigger()
