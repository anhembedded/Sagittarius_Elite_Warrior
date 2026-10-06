"""Keeps a mode's chart commands in step with the chart in front (`BOT-156`).

The commands (`chart_commands.py`) are the shell's actions; the chart's own
are its toolbar's. A command drives the chart's action, and the chart's
action says back whether it is enabled (Go live is off while the chart
follows the live edge) and, for Box zoom, checked. With no chart in front
every command is off. A mode follows a new chart whenever the one in front
changes; the previous chart's connections are dropped, so a closed tab's
actions drive nothing.

Presenter-owned (`async-ui-action-rule.md` §2), never registered. The
mechanism is the shared `ActionMirror`; this names the chart's commands.
"""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import QObject
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
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_mirror import ActionMirror


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


class ChartCommandMirror(ActionMirror):
    """@brief A mode's chart commands, driving and following one chart."""

    def __init__(self, prefix: str, parent: QObject | None = None) -> None:
        super().__init__(
            {key: chart_command_id(prefix, key) for key in chart_command_keys()},
            parent,
        )

    def follow_chart(self, actions: Mapping[str, QAction] | None) -> None:
        """Follows `actions` (`chart_command_actions()` of the chart in
        front); `None` means no chart, and every command off."""
        self.follow(actions)
