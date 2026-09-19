"""`EPIC-025F` — the concrete `INavigationService` adapter, wrapping the
existing `PresenterManager` router without replacing it (`ScreenRegistry`
retirement is a later, separately-scoped step)."""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)
from sagittarius_engine.extensions.pyside_mvc import PresenterManager

from .ports.i_navigation_service import INavigationService


class NavigationService(INavigationService):
    """`can_leave` is the seam `Docs/HLD/05_engine_app_split.md` §5.2 calls
    for, built now and wired permissive (`architecture-rule.md` §7.2.1 —
    "seam now, variant later"): no screen today needs to block navigation,
    so the default `None` accepts every request. A future screen with
    unsaved state supplies a callable; nothing about this class changes."""

    def __init__(
        self,
        router: PresenterManager,
        *,
        can_leave: Callable[[], bool] | None = None,
    ) -> None:
        self._router = router
        self._can_leave = can_leave
        self._current_source: NavigationSource | None = None

    def navigate(self, route: str, *, source: NavigationSource) -> bool:
        if self._can_leave is not None and not self._can_leave():
            return False
        self._router.navigate_to(route)
        self._current_source = source
        return True

    @property
    def current_source(self) -> NavigationSource | None:
        return self._current_source
