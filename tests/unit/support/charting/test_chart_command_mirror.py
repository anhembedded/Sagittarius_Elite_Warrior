"""A chart's toolbar actions as menu commands (`BOT-156`): the commands drive
the chart in front and follow its enabled and checked state; a chart no
longer in front drives nothing, and with no chart every command is off."""

from __future__ import annotations

import pytest
import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, QObject
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.chart_command_mirror import (
    ChartCommandMirror,
    chart_command_actions,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_commands import (
    BOX_ZOOM,
    GO_LIVE,
    MENU_EQUIVALENT,
    ZOOM_IN,
    ZOOM_OUT,
    chart_command_id,
    chart_command_keys,
    chart_commands,
)
from Sagittarius_Elite_Warrior.tests.command_actions import bound_actions
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_widget_checks import (
    command_name,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.action_text import (
    access_keys,
)

_PREFIX = "test.chart"
_MENU = ("&View", "C&hart")


@pytest.fixture
def menu(qapp):
    """The shell's actions for the chart commands, bound to a mirror, and
    two charts the mode could show."""
    owner = QObject()
    mirror = ChartCommandMirror(_PREFIX, owner)
    registry = bound_actions(
        owner, chart_commands("test", _PREFIX, "test", _MENU), mirror.bind_commands
    )
    actions = {
        key: registry.action(chart_command_id(_PREFIX, key))
        for key in chart_command_keys()
    }
    first, second = ChartCard("BTCUSDT"), ChartCard("ETHUSDT")
    yield mirror, actions, first, second
    for widget in (first, second):
        if shiboken6.isValid(widget):
            widget.deleteLater()
    owner.deleteLater()


def test_every_command_is_off_until_a_chart_is_followed(menu):
    _mirror, actions, _first, _second = menu

    assert not any(action.isEnabled() for action in actions.values())


def test_a_command_drives_the_chart_in_front(menu):
    mirror, actions, first, _second = menu
    mirror.follow_chart(chart_command_actions(first))
    zoomed: list[str] = []
    first.zoom.zoom_in.triggered.connect(lambda: zoomed.append("in"))

    actions[ZOOM_IN].trigger()

    assert len(zoomed) == 1


def test_go_live_is_off_while_the_chart_follows_the_newest_candle(menu):
    mirror, actions, first, _second = menu
    mirror.follow_chart(chart_command_actions(first))
    assert actions[ZOOM_IN].isEnabled()
    assert not actions[GO_LIVE].isEnabled()

    first.viewport.go_live.setEnabled(True)
    assert actions[GO_LIVE].isEnabled()

    actions[GO_LIVE].trigger()
    assert not first.viewport.go_live.isEnabled()
    assert not actions[GO_LIVE].isEnabled()


def test_box_zoom_is_checked_in_the_menu_and_on_the_chart_alike(menu):
    mirror, actions, first, _second = menu
    mirror.follow_chart(chart_command_actions(first))

    actions[BOX_ZOOM].trigger()
    assert first.zoom.box_zoom.isChecked()

    first.zoom.box_zoom.setChecked(False)
    assert not actions[BOX_ZOOM].isChecked()


def test_a_chart_no_longer_in_front_is_neither_driven_nor_followed(menu):
    mirror, actions, first, second = menu
    mirror.follow_chart(chart_command_actions(first))
    mirror.follow_chart(chart_command_actions(second))
    zoomed: list[str] = []
    first.zoom.zoom_in.triggered.connect(lambda: zoomed.append("in"))

    actions[ZOOM_IN].trigger()
    first.viewport.go_live.setEnabled(True)

    assert zoomed == []
    assert not actions[GO_LIVE].isEnabled()


def test_with_no_chart_in_front_every_command_is_off(menu):
    mirror, actions, first, _second = menu
    mirror.follow_chart(chart_command_actions(first))

    mirror.follow_chart(None)

    assert not any(action.isEnabled() for action in actions.values())


def test_each_command_reads_as_the_toolbar_action_it_stands_for(menu):
    """The conformance suite matches a toolbar action to a menu command by
    its text (`toolbar_actions_in_a_menu`)."""
    _mirror, _actions, first, _second = menu
    texts = {
        command_name(c.text) for c in chart_commands("test", _PREFIX, "test", _MENU)
    }

    on_chart = chart_command_actions(first)

    assert {command_name(action.text()) for action in on_chart.values()} == texts


def test_a_pinned_timeframe_names_the_command_that_reaches_it(menu):
    _mirror, _actions, first, _second = menu
    timeframes = first.toolbar.timeframes
    more = command_name(timeframes.more_action.text())

    pinned = [
        action
        for action in first.toolbar.actions()
        if action.objectName().startswith("actTimeframe_")
    ]

    assert pinned
    assert all(
        command_name(str(action.property(MENU_EQUIVALENT))) == more for action in pinned
    )


def test_each_command_has_its_own_access_key():
    commands = chart_commands("test", _PREFIX, "test", _MENU)
    keys = [key for c in commands for key in access_keys(c.text)]

    assert len(keys) == len(set(keys)) == len(commands)


def test_a_chart_deleted_before_the_mode_follows_another_drives_nothing(menu, qapp):
    """Review of PR #372: the commands must not reach a deleted action,
    whatever order a host closes a chart and follows the next in."""
    mirror, actions, first, _second = menu
    mirror.follow_chart(chart_command_actions(first))

    first.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    actions[ZOOM_IN].trigger()

    assert not actions[ZOOM_IN].isEnabled()


def test_zoom_in_and_out_take_the_platform_s_zoom_keys():
    commands = {c.command_id: c for c in chart_commands("test", _PREFIX, "test", _MENU)}

    assert commands[chart_command_id(_PREFIX, ZOOM_IN)].standard_shortcut == "ZoomIn"
    assert commands[chart_command_id(_PREFIX, ZOOM_OUT)].standard_shortcut == "ZoomOut"
