"""`EPIC-040E` — the Bots mode's centre holds Live and Backtest; View → Live chart and View →
Backtest switch between them by keyboard; a tab that cannot be used is off and says why, never
hidden; and a window state saved before the change, with its Backtest dock, still loads."""

from __future__ import annotations

from PySide6.QtWidgets import QDockWidget, QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_commands import (
    BACKTEST_TAB,
    LIVE_TAB,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    BotsView,
    TabAvailability,
)

from .bots_screen_fixtures import stored

_BACKTEST = 1
_LIVE = 0


def test_the_live_tab_is_first_and_shown_at_start(qapp) -> None:
    view = BotsView()

    assert view.centre.currentIndex() == _LIVE
    assert view.centre.isTabEnabled(_BACKTEST)


def test_a_tab_that_is_off_says_why_and_is_never_hidden(qapp) -> None:
    view = BotsView()
    changes: list[bool] = []
    view.backtest_enabled_changed.connect(changes.append)

    view.set_backtest_available(
        TabAvailability(False, "The selected bot's kind has no backtest.")
    )

    assert not view.centre.isTabEnabled(_BACKTEST)
    assert view.centre.isTabVisible(_BACKTEST)
    assert (
        view.centre.tabToolTip(_BACKTEST) == "The selected bot's kind has no backtest."
    )
    assert changes == [False]

    view.set_backtest_available(TabAvailability(False, "again"))
    assert changes == [False]  # said once, on the change

    view.set_backtest_available(TabAvailability())
    assert view.centre.isTabEnabled(_BACKTEST) and changes == [False, True]


def test_a_tab_turned_off_while_shown_gives_way_to_live(qapp) -> None:
    view = BotsView()
    view.show_backtest()
    assert view.centre.currentIndex() == _BACKTEST

    view.set_backtest_available(TabAvailability(False, "no"))

    assert view.centre.currentIndex() == _LIVE
    view.show_backtest()
    assert view.centre.currentIndex() == _LIVE  # a tab that is off is not switched to


def test_the_view_commands_switch_the_tabs(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", BotLifecycleState.DRAFT)])
    screen.settle()

    screen.actions.action(BACKTEST_TAB).trigger()
    assert screen.view.centre.currentIndex() == _BACKTEST

    screen.actions.action(LIVE_TAB).trigger()
    assert screen.view.centre.currentIndex() == _LIVE


def test_view_backtest_is_off_with_the_tab_and_is_a_keyboard_shortcut(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", BotLifecycleState.DRAFT)])
    screen.settle()
    action = screen.actions.action(BACKTEST_TAB)
    assert action.shortcut().toString() == "Ctrl+J"
    assert action.isEnabled()

    screen.view.set_backtest_available(TabAvailability(False, "no"))

    assert not action.isEnabled()


def test_a_window_state_saved_with_the_old_backtest_dock_still_loads(qapp) -> None:
    """Before `EPIC-040E` Backtest was a bottom dock; Qt restores docks by object name and skips a
    name the window no longer has, so the rest of the layout comes back."""
    old = BotsView()
    old.surface.place_widget(Place.CONSOLE, QWidget(), title="Backtest")
    saved = old.surface.saveState()
    titles = {dock.windowTitle() for dock in old.surface.findChildren(QDockWidget)}
    assert "Backtest" in titles

    fresh = BotsView()
    assert fresh.surface.restoreState(saved)

    restored = {dock.windowTitle() for dock in fresh.surface.findChildren(QDockWidget)}
    assert "Backtest" not in restored
    assert {"Bots", "Plan", "Orders", "Fills", "Log"} <= restored
    assert fresh.surface.centralWidget() is fresh.centre
