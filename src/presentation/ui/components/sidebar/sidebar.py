from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget
from sagittarius_engine.extensions.pyside_mvc import QmlHostView

from .nav_section import NavSection
from .sidebar_view_model import SidebarViewModel

_MAX_WIDTH = 250
_EXPANDED_WIDTH = 220
_COLLAPSED_WIDTH = 64


class Sidebar(QmlHostView):
    """
    @brief Self-contained navigation sidebar — QML-rendered, QWidget-hosted.

    @details
    Follows SRP: renders nav entries and tracks the active route. Navigation
    decisions are communicated upward via sig_navigate — this component knows
    nothing about screens or the router.

    Its Python-facing contract (`sig_navigate`, `set_active`) is unchanged
    from the QtWidgets version it replaces, so MainWindow's wiring and
    `switch_screen()` needed no changes when it moved to QML.

    Usage:
        sections = [
            NavSection("NAVIGATION", (
                NavItem("Dev Board", "dashboard", "layout-dashboard"),
            )),
        ]
        sidebar = Sidebar(sections=sections)
        sidebar.sig_navigate.connect(main_window.switch_screen)
        sidebar.set_active("dashboard")
    """

    QML_DIR = Path(__file__).parent

    #: Emitted when the user activates a navigable entry. Carries the route name.
    sig_navigate = Signal(str)

    def __init__(
        self,
        sections: Sequence[NavSection],
        bottom_actions: Sequence = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setMinimumWidth(_COLLAPSED_WIDTH)
        self.setMaximumWidth(_MAX_WIDTH)

        view_model = SidebarViewModel(sections, bottom_actions)
        # Re-emitted rather than exposing the view model, so callers depend on
        # this component's signal instead of reaching into its internals.
        view_model.navigationRequested.connect(self.sig_navigate)
        view_model.isCollapsedChanged.connect(self._on_collapsed_changed)

        self.set_view_model(view_model)
        self.load_qml("Sidebar.qml")
        self._on_collapsed_changed()

    def _on_collapsed_changed(self) -> None:
        if self._view_model and self._view_model.isCollapsed:
            self.setFixedWidth(_COLLAPSED_WIDTH)
        else:
            self.setMinimumWidth(_COLLAPSED_WIDTH)
            self.setMaximumWidth(_MAX_WIDTH)
            self.resize(_EXPANDED_WIDTH, self.height())

    def set_active(self, route_name: str) -> None:
        """
        @brief Marks a route as the active/highlighted entry.
        @param route_name The currently active route.
        """
        self._view_model.set_active_route(route_name)
