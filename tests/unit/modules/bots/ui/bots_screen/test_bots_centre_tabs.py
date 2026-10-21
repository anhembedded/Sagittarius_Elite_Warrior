"""`EPIC-040E` — the Bots mode's centre holds Live and Backtest; View → Live chart and View →
Backtest switch between them by keyboard; a tab that cannot be used is off and says why, never
hidden; and a window state saved before the change, with its Backtest dock, still loads."""

from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDockWidget, QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_command_binding import (
    bind_bots_commands,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_commands import (
    BACKTEST_TAB,
    LIVE_TAB,
    bots_commands,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_screen import (
    BOTS_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    BotsView,
    TabAvailability,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view_model import (
    BotsViewModel,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.command_actions import bound_actions
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.ui.strategies.strategy_fakes import (
    VenueArming,
    venue_strategies,
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
    """Before `EPIC-040E` Backtest was a bottom dock tabbed with Orders, Ladder and Fills. Qt
    restores docks by object name and skips a name the window no longer has, so what the person
    arranged comes back: the tab group, a dock they had hidden, and the tabbed centre."""
    old = BotsView()
    stale = old.surface.place_widget(Place.CONSOLE, QWidget(), title="Backtest")
    del stale
    orders = old.surface.dock_of(old.orders)
    backtest = next(
        dock
        for dock in old.surface.findChildren(QDockWidget)
        if dock.windowTitle() == "Backtest"
    )
    old.surface.tabifyDockWidget(orders, backtest)
    old.surface.dock_of(old.log).hide()
    saved = old.surface.save_perspective()
    assert backtest in old.surface.tabifiedDockWidgets(orders)

    fresh = BotsView()
    assert fresh.surface.restore_perspective(saved)

    docks = {
        dock.windowTitle(): dock for dock in fresh.surface.findChildren(QDockWidget)
    }
    assert "Backtest" not in docks
    assert docks["Log"].isHidden()
    tabbed = {
        dock.windowTitle()
        for dock in fresh.surface.tabifiedDockWidgets(
            fresh.surface.dock_of(fresh.orders)
        )
    }
    assert {"Ladder", "Fills"} <= tabbed
    assert fresh.surface.centralWidget() is fresh.centre


def test_a_tab_that_is_off_before_the_commands_are_bound_starts_off(qapp) -> None:
    """The first bot followed may already be one the workbench cannot replay: the command takes
    the tab's state at binding, not an assumed on."""
    view = BotsView()
    view.set_backtest_available(TabAvailability(False, "no"))
    actions = bound_actions(
        QObject(),
        bots_commands(BOTS_ROUTE),
        lambda binder: bind_bots_commands(
            binder,
            BotsViewModel(),
            venue_strategies((VenueArming(TradingVenue.SPOT_TESTNET),)),
            None,
            view,
        ),
    )

    assert not actions.action(BACKTEST_TAB).isEnabled()
