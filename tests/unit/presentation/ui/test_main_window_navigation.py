"""`EPIC-025F` PR 5.5 — `MainWindow` navigation service integration."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import MainWindow
from Sagittarius_Elite_Warrior.src.support.ui_kit.registry import (
    INavigationService,
    IScreenRegistry,
    NavigationService,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.sidebar import ISidebar


@pytest.fixture
def dummy_harness(qtbot):
    app_engine = Mock()
    app_engine.context.container = Mock()

    screen_registry = Mock(spec=IScreenRegistry)
    screen_registry.get_default_route.return_value = "welcome"
    screen_registry.build_sidebar_navigation.return_value = ((), ())

    sidebar_widget = QWidget()
    sidebar = Mock(spec=ISidebar)
    sidebar.sig_navigate = Mock()
    sidebar.collapsed_changed = Mock()
    sidebar.is_collapsed = False
    # Sidebar factory returns QWidget that also conforms to ISidebar interface in Qt hierarchy
    sidebar_factory = Mock(return_value=sidebar_widget)
    sidebar_widget.sig_navigate = Mock()
    sidebar_widget.collapsed_changed = Mock()
    sidebar_widget.is_collapsed = False
    sidebar_widget.set_active = Mock()

    return app_engine, screen_registry, sidebar_factory, sidebar_widget


def test_main_window_creates_default_navigation_service(dummy_harness, qtbot) -> None:
    app_engine, screen_registry, sidebar_factory, _sidebar = dummy_harness

    with patch(
        "Sagittarius_Elite_Warrior.src.presentation.ui.main_window.PresenterManager"
    ):
        window = MainWindow(app_engine, screen_registry, sidebar_factory)
        qtbot.addWidget(window)

        assert isinstance(window.navigation_service, INavigationService)
        assert isinstance(window.navigation_service, NavigationService)


def test_main_window_accepts_injected_navigation_service(dummy_harness, qtbot) -> None:
    app_engine, screen_registry, sidebar_factory, sidebar_widget = dummy_harness
    custom_nav = Mock(spec=INavigationService)
    custom_nav.navigate.return_value = True

    with patch(
        "Sagittarius_Elite_Warrior.src.presentation.ui.main_window.PresenterManager"
    ):
        window = MainWindow(
            app_engine,
            screen_registry,
            sidebar_factory,
            navigation_service=custom_nav,
        )
        qtbot.addWidget(window)

        assert window.navigation_service is custom_nav
        # Boot initial navigation tags RESTORE
        custom_nav.navigate.assert_called_with(
            "welcome", source=NavigationSource.RESTORE
        )

        # Explicit switch screen tags USER_INTENT
        window.switch_screen("trading")
        custom_nav.navigate.assert_called_with(
            "trading", source=NavigationSource.USER_INTENT
        )
        sidebar_widget.set_active.assert_called_with("trading")
