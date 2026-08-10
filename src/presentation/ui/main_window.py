"""
@brief MainWindow — the application shell and screen router.

@details
Single responsibility: assemble the Sidebar, QStackedWidget, and
PresenterManager, then wire navigation signals between them.

Engine boot, QApplication setup, and theming live in app_bootstrapper.py.
Screen-specific factory/presenter imports stay at the top level (no local imports).
"""

from __future__ import annotations

from Binace_Bot.src.presentation.ui.components.sidebar import (
    NavItem,
    NavSection,
    Sidebar,
)
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
from Binace_Bot.src.presentation.ui.screens.settings.settings_presenter import (
    SettingsPresenter,
)
from Binace_Bot.src.presentation.ui.screens.settings.settings_view import (
    SettingsView,
)
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QStackedWidget, QWidget
from sagittarius_engine.extensions.pyside_mvc import PresenterManager

# ---------------------------------------------------------------------------
# Navigation sections. A NavItem with route=None is a placeholder for a screen
# that doesn't exist yet (e.g. "Backtest Engine" — BOT-021/022 still backlog);
# those are never navigable regardless of `enabled` (see NavItem.is_navigable).
# Adding a new screen: add one entry here and register it in _setup_router().
# ---------------------------------------------------------------------------
_NAV_SECTIONS = [
    NavSection(
        "NAVIGATION",
        (
            NavItem("Dev Board", "dashboard", "layout-dashboard"),
            NavItem("Database", "data_management", "database"),
        ),
    ),
    NavSection(
        "QUANT ENGINE",
        (
            NavItem("Backtest Engine", None, "bar-chart-2", enabled=False),
            NavItem("API & Credentials", "settings", "settings"),
        ),
    ),
]

_WINDOW_TITLE = "Sagittarius Elite Warrior — Binance Trading Bot"
# 1200x800 used to be enough, but the Dev Board's right column has grown
# (System Controls + Indicators + System Monitor) — a bigger default avoids
# content being clipped the instant the window opens, before the user ever
# touches the (now resizable) splitter.
_WINDOW_SIZE = (1440, 860)
_CONTENT_BG_STYLE = "background-color: #0a0a0c; color: #e8e9ec;"


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
        self._sidebar = Sidebar(sections=_NAV_SECTIONS)
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
        self._router.register(
            "settings",
            SettingsPresenter,
            lambda: SettingsView(),
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
    from Binace_Bot.src.presentation.ui.app_bootstrapper import main

    main()
