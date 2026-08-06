"""
@brief MainWindow — the application shell and screen router.

@details
Single responsibility: assemble the Sidebar, QStackedWidget, and
PresenterManager, then wire navigation signals between them.

Engine boot, QApplication setup, and theming live in app_bootstrapper.py.
Screen-specific factory/presenter imports stay at the top level (no local imports).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QStackedWidget, QWidget

from sagittarius_engine.extensions.pyside_mvc import PresenterManager

from Binace_Bot.src.presentation.ui.components.sidebar import Sidebar
from Binace_Bot.src.presentation.ui.screens.dashboard.dashboard_presenter import (
    DashboardPresenter,
)
from Binace_Bot.src.presentation.ui.screens.dashboard.dashboard_view import (
    DashboardView,
)
from Binace_Bot.src.presentation.ui.screens.data_management.data_management_presenter import (
    DataManagementPresenter,
)
from Binace_Bot.src.presentation.ui.screens.data_management.data_management_view import (
    DataManagementView,
)

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Navigation routes — (display_label, route_name)
# Adding a new screen: add one entry here and register it in _setup_router().
# ---------------------------------------------------------------------------
_NAV_ROUTES = [
    ("Dashboard", "dashboard"),
    ("Database", "data_management"),
]

_WINDOW_TITLE = "Binance Bot Desktop - Clean Architecture"
_WINDOW_SIZE = (1200, 800)
_CONTENT_BG_STYLE = "background-color: #1e1e1e; color: white;"


class MainWindow(QMainWindow):
    """
    @brief The application shell: navigation sidebar + screen router.

    @details
    Owns only assembly logic:
    - Creates the Sidebar component and wires sig_navigate → switch_screen.
    - Creates the PresenterManager (router) and registers all screens.
    - Routes switch_screen calls from Sidebar to the router and back.
    """

    def __init__(self, app_engine) -> None:
        super().__init__()
        self._app = app_engine
        self.setWindowTitle(_WINDOW_TITLE)
        self.resize(*_WINDOW_SIZE)

        # ---- Shell layout ------------------------------------------------
        central = QWidget()
        self.setCentralWidget(central)
        shell_layout = QHBoxLayout(central)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        # ---- Sidebar component -------------------------------------------
        self._sidebar = Sidebar(routes=_NAV_ROUTES)
        self._sidebar.sig_navigate.connect(self.switch_screen)

        # ---- Content area -----------------------------------------------
        self._stacked = QStackedWidget()
        self._stacked.setStyleSheet(_CONTENT_BG_STYLE)

        shell_layout.addWidget(self._sidebar)
        shell_layout.addWidget(self._stacked)

        # ---- Router setup -----------------------------------------------
        self._setup_router()

        # ---- Navigate to default screen ---------------------------------
        self.switch_screen("dashboard")

    def _setup_router(self) -> None:
        """Register all screens with the lazy-loading PresenterManager."""
        self._router = PresenterManager(self._app.context.container, self._stacked)

        self._router.register(
            "dashboard",
            DashboardPresenter,
            lambda: DashboardView(),
        )
        self._router.register(
            "data_management",
            DataManagementPresenter,
            lambda: DataManagementView(),
        )

    def switch_screen(self, route_name: str) -> None:
        """
        @brief Navigate to a registered screen and sync the sidebar active state.
        @param route_name The route key registered with the PresenterManager.
        """
        self._router.navigate_to(route_name)
        self._sidebar.set_active(route_name)


# ---------------------------------------------------------------------------
# Legacy entry point — kept so that existing test imports from this module
# (test_sanity_ui_e2e.py) continue to work without modification.
# New code should use app_bootstrapper.main() instead.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from Binace_Bot.src.presentation.ui.app_bootstrapper import main as main
    main()
