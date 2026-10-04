"""`EPIC-033C` — the workbench window: every navigable screen is a mode, the
last mode comes back, and a mode hears why it was shown.

The window is built against a real `ScreenRegistry` and a real
`UiStateCoordinator` over an in-memory store; only the presenters are
doubles, and they implement exactly what the window calls on them.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel
from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import MainWindow
from Sagittarius_Elite_Warrior.src.support.ui_kit.registry import INavigationService
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.adapters.in_memory_state_store import (
    InMemoryStateStore,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.ui_state_coordinator import (
    UiStateCoordinator,
)
from Sagittarius_Elite_Warrior.tests.unit.presentation.ui.main_window_fakes import (
    DisposeLog,
    engine,
    presenter,
    three_screens,
)


@pytest.fixture
def log() -> DisposeLog:
    return DisposeLog()


@pytest.fixture
def window(qtbot, log: DisposeLog) -> MainWindow:
    built = MainWindow(engine(), three_screens(log), venue_text="SPOT TESTNET")
    qtbot.addWidget(built)
    return built


def test_every_navigable_screen_is_a_mode_in_registry_order(window: MainWindow) -> None:
    assert window.navigation.modes() == ("trading.futures", "trading.spot", "settings")


def test_each_mode_has_a_view_menu_item_with_its_own_access_key(
    window: MainWindow,
) -> None:
    texts = [
        action.text()
        for action in window.menu("&View").actions()
        if action.isCheckable()
        and action.text().replace("&", "")
        in {
            "Futures",
            "Spot",
            "Settings",
        }
    ]
    assert texts == ["&Futures", "&Spot", "S&ettings"]


def test_the_first_run_opens_the_default_mode_as_a_restore(window: MainWindow) -> None:
    assert window.current_mode == "trading.futures"
    assert presenter(window, "trading.futures").shown == [NavigationSource.RESTORE]
    assert presenter(window, "trading.spot").shown == []
    assert window.navigation_service.current_source is NavigationSource.RESTORE


def test_a_click_is_user_intent_and_reaches_the_mode_shown(window: MainWindow) -> None:
    assert window.switch_screen("trading.spot") is True

    assert window.current_mode == "trading.spot"
    assert presenter(window, "trading.spot").shown == [NavigationSource.USER_INTENT]
    assert window.navigation_service.current_source is NavigationSource.USER_INTENT


def test_a_click_on_the_showing_mode_still_reaches_it_as_user_intent(
    window: MainWindow,
) -> None:
    """A mode restored at start waits for a click to go live (`BUG-104`);
    clicking that same mode must deliver one, though nothing on the stack
    changes."""
    assert window.switch_screen("trading.futures") is True

    assert presenter(window, "trading.futures").shown == [
        NavigationSource.RESTORE,
        NavigationSource.USER_INTENT,
    ]


def test_the_mode_bar_action_is_a_click_too(window: MainWindow) -> None:
    mode_action = next(
        action for action in window.menu("&View").actions() if action.text() == "&Spot"
    )
    mode_action.trigger()

    assert presenter(window, "trading.spot").shown == [NavigationSource.USER_INTENT]


def test_the_navigation_port_passes_its_source_through(window: MainWindow) -> None:
    service = window.navigation_service
    assert isinstance(service, INavigationService)

    assert service.navigate("trading.spot", source=NavigationSource.RESTORE) is True

    assert presenter(window, "trading.spot").shown == [NavigationSource.RESTORE]


def test_a_mode_without_on_mode_shown_still_shows(window: MainWindow) -> None:
    assert window.switch_screen("settings") is True
    assert window.current_mode == "settings"


def test_the_venue_is_in_the_title_and_the_status_bar(window: MainWindow) -> None:
    assert window.windowTitle() == "Sagittarius Elite Warrior — SPOT TESTNET"
    label = window.findChild(QLabel, "workbench::venue")
    assert label is not None
    assert label.text() == "SPOT TESTNET"


def test_shutdown_disposes_every_presenter_last_built_first_once(
    window: MainWindow, log: DisposeLog
) -> None:
    window.shutdown()
    window.shutdown()

    assert log.routes == ["settings", "trading.spot", "trading.futures"]


def test_the_last_mode_comes_back_as_a_restore(qtbot) -> None:
    coordinator = UiStateCoordinator(InMemoryStateStore())
    first = MainWindow(
        engine(), three_screens(DisposeLog()), state_coordinator=coordinator
    )
    qtbot.addWidget(first)
    first.switch_screen("trading.spot")
    first.shutdown()

    second = MainWindow(
        engine(), three_screens(DisposeLog()), state_coordinator=coordinator
    )
    qtbot.addWidget(second)

    assert second.current_mode == "trading.spot"
    assert presenter(second, "trading.spot").shown == [NavigationSource.RESTORE]
    assert presenter(second, "trading.futures").shown == []


def test_a_saved_mode_that_no_longer_exists_opens_the_default(qtbot) -> None:
    coordinator = UiStateCoordinator(InMemoryStateStore())
    first = MainWindow(
        engine(), three_screens(DisposeLog()), state_coordinator=coordinator
    )
    qtbot.addWidget(first)
    saved = dict(first.capture_state())
    saved["mode"] = "retired.mode"

    second = MainWindow(engine(), three_screens(DisposeLog()))
    qtbot.addWidget(second)
    second.restore_state(saved)

    assert second.current_mode == "trading.futures"
