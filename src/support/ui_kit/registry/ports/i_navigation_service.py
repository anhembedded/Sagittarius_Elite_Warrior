"""`EPIC-025F` — how the application asks the window to show a mode. `abc.ABC`:
none of `architecture-rule.md` §2.1's Protocol exceptions apply to its adapter.

Prototyped here against the `PresenterManager` router (`Docs/HLD/05_engine_app_split.md`
§5.2, ❓O2) and then built in the Engine as `WorkbenchShell`'s `NavigationService`
(`TASK-043` E3). Since `EPIC-033C` the adapter is
`presentation/ui/shell_navigation.py`, over the workbench window.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)


class INavigationService(ABC):
    """Navigates between registered routes, tracking why the last
    navigation happened so a screen can distinguish a real user click from
    the shell replaying a remembered route (`BUG-104`, `BUG-107`)."""

    @abstractmethod
    def navigate(self, route: str, *, source: NavigationSource) -> bool:
        """Navigates to `route`. Returns `True` if the navigation happened,
        `False` if a `can_leave` guard on the current screen refused it (no
        screen currently installs one — see the seam's own docstring)."""
        ...

    @property
    @abstractmethod
    def current_source(self) -> NavigationSource | None:
        """The `source` of the most recent successful `navigate()` call, or
        `None` before the first one."""
        ...
