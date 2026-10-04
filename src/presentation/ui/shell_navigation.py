"""The concrete `INavigationService`: the workbench window's own navigation
(`EPIC-033C`), behind the port the application already depends on.

`EPIC-025F` wrapped the `PresenterManager` router; the router is gone and the
Engine's `WorkbenchShell` switches modes now. Its `NavigationService` holds the
per-mode `can_leave` seam the old adapter kept as one global callable, so the
seam moved with the mechanism rather than being duplicated.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.registry import INavigationService
from sagittarius_engine.extensions.pyside_mvc.workbench.navigation_service import (
    NavigationSource as ShellNavigationSource,
)

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import MainWindow


def to_shell_source(source: NavigationSource) -> ShellNavigationSource:
    """The application's `NavigationSource` as the Engine's: one enum per
    side of the boundary, the same two members by name."""
    return ShellNavigationSource[source.name]


def from_shell_source(source: ShellNavigationSource) -> NavigationSource:
    return NavigationSource[source.name]


class ShellNavigation(INavigationService):
    """Navigates the window between modes; the window remembers why, since a
    mode-bar click never passes through here."""

    def __init__(self, window: MainWindow) -> None:
        self._window = window

    def navigate(self, route: str, *, source: NavigationSource) -> bool:
        return self._window.navigate(route, to_shell_source(source))

    @property
    def current_source(self) -> NavigationSource | None:
        last = self._window.last_source
        return from_shell_source(last) if last is not None else None
