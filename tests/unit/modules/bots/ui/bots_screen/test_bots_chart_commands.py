"""`EPIC-040` F1 — View → Chart in the Bots mode: More timeframes… (and the zoom) reach the chart in
front by keyboard, as they do in Market and Backtest.

The Bots mode shows one of two things in front: the selected bot's Live chart, or the Backtest
tab's workbench, whose interval row is the only timeframe chooser there. Each test is the real
presenter over the real commands as the window binds them (`open_bots_screen`); a note in either
tab leaves every command off."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench_view import (
    BacktestWorkbenchView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_commands import (
    CHART_MENU,
    CHART_PREFIX,
    bots_commands,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_screen import (
    BOTS_ROUTE,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.chart_commands import (
    MORE_TIMEFRAMES,
    ZOOM_IN,
    chart_command_id,
)

from .bots_screen_fixtures import BotsScreen, stored
from .connect_screen_helpers import select

_BACKTEST = 1
_LIVE = 0


def _command(screen: BotsScreen, key: str):
    return screen.actions.action(chart_command_id(CHART_PREFIX, key))


def _opened(open_bots_screen) -> BotsScreen:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    select(screen, "a00001")
    screen.settle()
    return screen


def test_the_chart_commands_are_contributed_to_the_bots_mode_in_view_chart() -> None:
    contributed = [
        command
        for command in bots_commands(BOTS_ROUTE)
        if command.command_id == chart_command_id(CHART_PREFIX, MORE_TIMEFRAMES)
    ]

    assert len(contributed) == 1
    assert contributed[0].menu_path == CHART_MENU
    assert contributed[0].mode == BOTS_ROUTE
    assert contributed[0].needs_input


def test_with_no_bot_selected_every_chart_command_is_off(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()

    assert not _command(screen, MORE_TIMEFRAMES).isEnabled()
    assert not _command(screen, ZOOM_IN).isEnabled()


def test_on_the_live_tab_more_timeframes_drives_the_bots_chart(
    open_bots_screen,
) -> None:
    screen = _opened(open_bots_screen)
    card = next(iter(screen.view.chart_area.findChildren(ChartCard)))
    asked: list[bool] = []
    card.toolbar.timeframes.more_requested.connect(lambda: asked.append(True))

    command = _command(screen, MORE_TIMEFRAMES)
    assert command.isEnabled()
    command.trigger()

    assert asked == [True]
    assert _command(screen, ZOOM_IN).isEnabled()


def test_on_the_backtest_tab_more_timeframes_drives_the_interval_row(
    open_bots_screen,
) -> None:
    screen = _opened(open_bots_screen)
    page = screen.view.shown_backtest_page()
    assert isinstance(page, BacktestWorkbenchView)
    asked: list[bool] = []
    page.interval.timeframes.more_requested.connect(lambda: asked.append(True))

    screen.view.show_backtest()
    assert screen.view.centre.currentIndex() == _BACKTEST
    command = _command(screen, MORE_TIMEFRAMES)
    assert command.isEnabled()
    command.trigger()

    assert asked == [True]
    # The result chart has no timeframe row and the interval row has no zoom.
    assert not _command(screen, ZOOM_IN).isEnabled()


def test_going_back_to_the_live_tab_gives_the_commands_back_to_its_chart(
    open_bots_screen,
) -> None:
    screen = _opened(open_bots_screen)
    screen.view.show_backtest()
    assert not _command(screen, ZOOM_IN).isEnabled()

    screen.view.show_live()

    assert screen.view.centre.currentIndex() == _LIVE
    assert _command(screen, ZOOM_IN).isEnabled()


def test_a_backtest_tab_that_shows_a_note_leaves_the_commands_off(
    open_bots_screen,
) -> None:
    screen = _opened(open_bots_screen)
    screen.view.show_backtest()
    assert _command(screen, MORE_TIMEFRAMES).isEnabled()

    screen.view.set_backtest_page(None, "The selected bot's kind has no backtest.")

    assert not _command(screen, MORE_TIMEFRAMES).isEnabled()
