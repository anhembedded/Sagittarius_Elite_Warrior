"""Screens for `MainWindow` tests: real `ScreenDescriptor`s in a real
`ScreenRegistry`, with presenters that record what the window tells them.

The window's contract with a presenter is `dispose()` (`BasePresenter`) and,
optionally, `IShownAsMode.on_mode_shown()`; the two doubles below implement
exactly that, one with the optional half and one without.
"""

from __future__ import annotations

from unittest.mock import Mock

from PySide6.QtWidgets import QLabel, QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.nav_metadata import (
    NavLocation,
    NavMetadata,
)
from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import MainWindow
from Sagittarius_Elite_Warrior.src.support.ui_kit.registry import (
    ScreenDescriptor,
    ScreenRegistry,
)


class DisposeLog:
    """Which presenters were disposed, in order, across one window."""

    def __init__(self) -> None:
        self.routes: list[str] = []


class PlainPresenter:
    """A presenter with no `on_mode_shown`: nothing goes live when shown."""

    def __init__(self, route: str, log: DisposeLog) -> None:
        self.route = route
        self._log = log

    def dispose(self) -> None:
        self._log.routes.append(self.route)


class ShownPresenter(PlainPresenter):
    """A presenter that goes live when shown (`IShownAsMode`)."""

    def __init__(self, route: str, log: DisposeLog) -> None:
        super().__init__(route, log)
        self.shown: list[NavigationSource] = []

    def on_mode_shown(self, source: NavigationSource) -> None:
        self.shown.append(source)


def screen(
    route: str,
    title: str,
    log: DisposeLog,
    *,
    item_sequence: int,
    is_default: bool = False,
    location: NavLocation = NavLocation.TOP_SECTION,
    shown: bool = True,
) -> ScreenDescriptor:
    presenter_type = ShownPresenter if shown else PlainPresenter
    return ScreenDescriptor(
        route=route,
        presenter_class=lambda view, container: presenter_type(route, log),
        view_factory=lambda: QLabel(title),
        nav=NavMetadata(
            title=title, icon="circle", item_sequence=item_sequence, location=location
        ),
        is_default=is_default,
    )


def three_screens(log: DisposeLog) -> ScreenRegistry:
    """Futures (the default), Spot, and Settings at the bottom with no
    `on_mode_shown`, registered out of order."""
    registry = ScreenRegistry()
    registry.register(
        screen(
            "settings",
            "Settings",
            log,
            item_sequence=10,
            location=NavLocation.BOTTOM_ACTION,
            shown=False,
        )
    )
    registry.register(screen("trading.spot", "Spot", log, item_sequence=17))
    registry.register(
        screen("trading.futures", "Futures", log, item_sequence=16, is_default=True)
    )
    return registry


def engine() -> Mock:
    app_engine = Mock()
    app_engine.context.container = Mock()
    return app_engine


def presenter(window: MainWindow, route: str) -> ShownPresenter:
    found = window.presenters[route]
    assert isinstance(found, ShownPresenter)
    return found


def view(window: MainWindow, route: str) -> QWidget:
    return window.hosts[route].view
