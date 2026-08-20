from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import Property, QObject, Signal, Slot

from .tab_interface import ITab
from .tabs import SidebarSection


class SidebarViewModel(QObject):
    """
    @brief QML-facing model for the navigation sidebar: exposes the nav
    structure and the active route, and turns QML clicks into a Python signal.

    @details
    Operates on open ITab abstractions and SidebarSection aggregates.
    Each tab exposes both `tab_full` and `tab_icon` representations,
    allowing clean rendering in both expanded and collapsed modes.
    """

    activeRouteChanged = Signal()
    isCollapsedChanged = Signal()

    #: Emitted when the user activates a navigable entry. Carries the route key.
    navigationRequested = Signal(str)

    def __init__(
        self,
        sections: Sequence[SidebarSection],
        bottom_actions: Sequence[ITab] = (),
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._sections = tuple(sections)
        self._bottom_actions = tuple(bottom_actions)
        self._active_route = ""
        self._is_collapsed = False

        routes = {
            item.route
            for section in self._sections
            for item in section.items
            if item.is_navigable and item.route
        }
        bottom_routes = {
            item.route
            for item in self._bottom_actions
            if item.is_navigable and item.route
        }
        self._navigable_routes = routes | bottom_routes

    @Property("QVariantList", constant=True)
    def sections(self) -> list[dict[str, Any]]:
        """Nav structure as plain dicts — the shape QML's Repeater consumes."""
        return [section.to_dict() for section in self._sections]

    @Property("QVariantList", constant=True)
    def bottomActions(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self._bottom_actions]

    def _get_active_route(self) -> str:
        return self._active_route

    activeRoute = Property(str, _get_active_route, notify=activeRouteChanged)

    def _get_is_collapsed(self) -> bool:
        return self._is_collapsed

    def _set_is_collapsed(self, value: bool) -> None:
        self.set_collapsed(value)

    isCollapsed = Property(
        bool, _get_is_collapsed, _set_is_collapsed, notify=isCollapsedChanged
    )

    def set_active_route(self, route: str) -> None:
        if route == self._active_route:
            return
        self._active_route = route
        self.activeRouteChanged.emit()

    @Slot(bool)
    def set_collapsed(self, collapsed: bool) -> None:
        val = bool(collapsed)
        if val == self._is_collapsed:
            return
        self._is_collapsed = val
        self.isCollapsedChanged.emit()

    @Slot()
    def toggleCollapsed(self) -> None:
        self.set_collapsed(not self._is_collapsed)

    @Slot(str)
    def navigate(self, route: str) -> None:
        """
        @brief Called from QML when an entry is clicked.
        @details Re-checks navigability in Python rather than trusting QML to
        have disabled the control — a routeless/disabled entry must never
        reach the router even if a future QML edit forgets the guard.
        """
        if route not in self._navigable_routes:
            return
        self.navigationRequested.emit(route)
