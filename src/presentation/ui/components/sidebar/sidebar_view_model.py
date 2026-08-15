from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Property, QObject, Signal, Slot

from .nav_section import NavSection


class SidebarViewModel(QObject):
    """
    @brief QML-facing model for the navigation sidebar: exposes the nav
    structure and the active route, and turns QML clicks into a Python signal.

    @details
    Deliberately a plain QObject rather than a BaseQmlViewModel: the sidebar
    is shell chrome with no FSM behind it, so inheriting that base would
    force an unused `uiMode` property onto it (Interface Segregation).

    `sections` is a constant Property — the nav structure is fixed at
    construction and never mutates at runtime, so declaring it `constant`
    states that contract to QML instead of implying a change signal that
    would never fire.
    """

    activeRouteChanged = Signal()

    #: Emitted when the user activates a navigable entry. Carries the route key.
    navigationRequested = Signal(str)

    def __init__(
        self, sections: Sequence[NavSection], bottom_actions: Sequence = (), parent=None
    ) -> None:
        super().__init__(parent)
        self._sections = tuple(sections)
        self._bottom_actions = tuple(bottom_actions)
        self._active_route = ""

        routes = {
            item.route
            for section in self._sections
            for item in section.items
            if item.is_navigable
        }
        bottom_routes = {
            item.route for item in self._bottom_actions if item.is_navigable
        }
        self._navigable_routes = routes | bottom_routes

    @Property("QVariantList", constant=True)
    def sections(self) -> list[dict]:
        """Nav structure as plain dicts — the shape QML's Repeater consumes
        (`modelData.label`, `modelData.route`, ...)."""
        return [
            {
                "title": section.title,
                "items": [
                    {
                        "label": item.label,
                        "route": item.route or "",
                        "icon": item.icon,
                        "navigable": item.is_navigable,
                    }
                    for item in section.items
                ],
            }
            for section in self._sections
        ]

    @Property("QVariantList", constant=True)
    def bottomActions(self) -> list[dict]:
        return [
            {
                "label": item.label,
                "route": item.route or "",
                "icon": item.icon,
                "navigable": item.is_navigable,
            }
            for item in self._bottom_actions
        ]

    def _get_active_route(self) -> str:
        return self._active_route

    activeRoute = Property(str, _get_active_route, notify=activeRouteChanged)

    def set_active_route(self, route: str) -> None:
        if route == self._active_route:
            return
        self._active_route = route
        self.activeRouteChanged.emit()

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
