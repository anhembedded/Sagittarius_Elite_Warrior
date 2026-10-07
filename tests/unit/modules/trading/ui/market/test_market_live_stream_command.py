"""`EPIC-034G` — View → Chart → Live stream: the chip's command in the menu
bar, acting on the Market chart in front. Checked while the chart connects or
is live; checking it goes live, unchecking it stops."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_commands import (
    CHART_PREFIX,
    market_commands,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_screen import (
    MARKET_ROUTE,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_commands import (
    chart_command_id,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_fsm_matrix import (
    LiveChartCommand,
    LiveChartState,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_stream_command import (
    LIVE_STREAM,
)
from Sagittarius_Elite_Warrior.tests.command_actions import bound_actions

S = LiveChartState


@pytest.fixture
def opened(build, threads, request):
    """The Market presenter with BTCUSDT open from a restore (History) and
    the shell's Live stream command bound."""
    presenter = build()
    owner = QObject()
    request.addfinalizer(owner.deleteLater)
    registry = bound_actions(
        owner, market_commands(MARKET_ROUTE), presenter.bind_commands
    )
    presenter.on_mode_shown(NavigationSource.RESTORE)
    threads.run_all()
    return presenter, registry.action(chart_command_id(CHART_PREFIX, LIVE_STREAM))


def test_the_command_is_unchecked_on_history_and_checking_it_goes_live(opened, threads):
    presenter, command = opened
    chart = presenter.charts["BTCUSDT"]
    assert chart.live_state is S.HISTORY and not command.isChecked()

    command.trigger()
    assert chart.live_state is S.CONNECTING and command.isChecked()
    threads.run_all()

    assert chart.live_state is S.LIVE and command.isChecked()


def test_unchecking_it_stops_the_stream(opened, threads):
    presenter, command = opened
    chart = presenter.charts["BTCUSDT"]
    command.trigger()
    threads.run_all()

    command.trigger()
    threads.run_all()

    assert chart.live_state is S.HISTORY and not command.isChecked()


def test_the_chips_own_command_moves_the_menu_entry(opened, threads):
    presenter, command = opened
    chart = presenter.charts["BTCUSDT"]

    chart.run_command(LiveChartCommand.GO_LIVE)
    threads.run_all()

    assert command.isChecked()


def test_the_command_is_off_once_no_chart_is_open(opened):
    presenter, command = opened

    presenter.view.chart_closed.emit("BTCUSDT")

    assert not command.isEnabled()
