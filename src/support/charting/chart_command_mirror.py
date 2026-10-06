"""Keeps a mode's chart commands in step with the chart in front (`BOT-156`).

The commands (`chart_commands.py`) are the shell's actions; the chart's own
are its toolbar's. A command drives the chart's action, and the chart's
action says back whether it is enabled (Go live is off while the chart
follows the live edge) and, for Box zoom, checked. With no chart in front
every command is off. A mode follows a new chart whenever the one in front
changes; the previous chart's connections are dropped, so a closed tab's
actions drive nothing.

Presenter-owned (`async-ui-action-rule.md` §2), never registered.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import partial

from PySide6.QtCore import QMetaObject, QObject, Signal
from PySide6.QtGui import QAction
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.chart_commands import (
    BOX_ZOOM,
    GO_LIVE,
    MORE_TIMEFRAMES,
    RESET_ZOOM,
    ZOOM_IN,
    ZOOM_IN_VERTICALLY,
    ZOOM_OUT,
    ZOOM_OUT_VERTICALLY,
    chart_command_id,
    chart_command_keys,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)


def chart_command_actions(card: ChartCard) -> dict[str, QAction]:
    """The chart's actions the commands drive, by key."""
    zoom = card.zoom
    return {
        MORE_TIMEFRAMES: card.toolbar.timeframes.more_action,
        ZOOM_IN: zoom.zoom_in,
        ZOOM_OUT: zoom.zoom_out,
        ZOOM_IN_VERTICALLY: zoom.zoom_in_vertically,
        ZOOM_OUT_VERTICALLY: zoom.zoom_out_vertically,
        BOX_ZOOM: zoom.box_zoom,
        RESET_ZOOM: zoom.reset_zoom,
        GO_LIVE: card.viewport.go_live,
    }


class _CommandState(QObject):
    checked = Signal(bool)
    enabled = Signal(bool)


class ChartCommandMirror(QObject):
    """@brief A mode's chart commands, driving and following one chart."""

    def __init__(self, prefix: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._prefix = prefix
        self._states = {key: _CommandState(self) for key in chart_command_keys()}
        self._actions: dict[str, QAction] = {}
        self._connections: list[QMetaObject.Connection] = []

    def bind_commands(self, binder: ICommandBinder) -> None:
        for key, state in self._states.items():
            binder.bind(
                chart_command_id(self._prefix, key),
                partial(self._on_command, key),
                enabled=state.enabled,
                checked=state.checked,
                initially_enabled=False,
            )

    def follow_chart(self, actions: Mapping[str, QAction] | None) -> None:
        """Follows `actions` (`chart_command_actions()` of the chart in
        front); `None` means no chart, and every command off."""
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
                action.destroyed.connect(partial(self._forget, key))
            )
            state.enabled.emit(action.isEnabled())
            state.checked.emit(action.isChecked())

    def _forget(self, key: str, *_destroyed: object) -> None:
        """A followed chart's action went with its chart before the mode
        followed another: the command drives nothing and is off, whatever
        order the host closes and re-follows in."""
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
