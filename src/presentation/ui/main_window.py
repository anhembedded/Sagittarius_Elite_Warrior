"""
@brief MainWindow — the application shell and screen router.

@details
Single responsibility: assemble the Sidebar, QStackedWidget, and
PresenterManager, then wire navigation signals between them.

Engine boot, QApplication setup, and theming live in app_bootstrapper.py.
Screen-specific factory/presenter imports stay at the top level (no local imports).

@par EPIC-010C — remembered shell state
`MainWindow` itself implements `IStateContributor` (structurally — it is a
`typing.Protocol`, so no base class or import-time coupling is needed) rather
than delegating to a helper object: window geometry, the active route, and
the sidebar's collapsed flag are `MainWindow`'s own fields, and
`code-quality-rule.md`'s Single-Scope Cohesion says a state that is this
tightly coupled to one object's own lifecycle belongs in that object, not
split across a second file. Window geometry is persisted as the real
`QByteArray` `saveGeometry()`/`restoreGeometry()` produce, base64-encoded —
`restoreGeometry()` already performs its own off-screen and DPI sanity
checks, so a hand-rolled `x/y/w/h` would buy no extra safety while getting
multi-monitor wrong in ways Qt already handles (`EPIC-010` design §5.6.3).
`state_coordinator` is optional and defaults to `None`: this app has no DI
container wiring for it yet (`010A`/`010B` are Elite-only, not yet promoted
to the Engine), and every existing caller that constructs a bare
`MainWindow(app_engine)` — several tests — must keep working unchanged.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray
from PySide6.QtGui import QCloseEvent, QMoveEvent, QResizeEvent
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QStackedWidget, QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette
from Sagittarius_Elite_Warrior.src.presentation.ui.components.sidebar import (
    NavItem,
    NavSection,
    Sidebar,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_presenter import (
    BackTestPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.view_factory import (
    build_backtest_view,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_presenter import (
    DashboardPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_view import (
    DashboardView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_presenter import (
    DataManagementPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_view import (
    DataManagementView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.settings.settings_presenter import (
    SettingsPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.settings.settings_view import (
    SettingsView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.state_scope import (
    StateData,
    StateScope,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.ui_state_coordinator import (
    UiStateCoordinator,
)
from sagittarius_engine.extensions.pyside_mvc import PresenterManager
from sagittarius_engine.interfaces.i_config import IConfig

# ---------------------------------------------------------------------------
# Navigation sections. A NavItem with route=None is a placeholder for a screen
# that doesn't exist yet; those are never navigable regardless of `enabled`
# (see NavItem.is_navigable). "Backtest Engine" got its real route once
# BackTestView/BackTestPresenter existed (BOT-022).
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
        (NavItem("Backtest Engine", "backtest", "bar-chart-2"),),
    ),
]

_BOTTOM_ACTIONS = (NavItem("API & Credentials", "settings", "settings"),)

_WINDOW_TITLE = "Sagittarius Elite Warrior — Binance Trading Bot"
# 1200x800 used to be enough, but the Dev Board's right column has grown
# (System Controls + Indicators + System Monitor) — a bigger default avoids
# content being clipped the instant the window opens, before the user ever
# touches the (now resizable) splitter.
_WINDOW_SIZE = (1440, 860)
#: Scoped to the stack itself. Written as a bare property list it was
#: `BUG-008` at the largest scope this app has — Qt reads a selector-less
#: rule as the universal selector, and this widget holds **every screen**,
#: so `Palette.BG` was repainted onto every label, field and frame in the
#: app that had no background rule of its own. That is what put a dark
#: rectangle behind each label in the storage screen's stat tiles.
_CONTENT_BG_STYLE = (
    f"QStackedWidget {{ background-color: {Palette.BG}; "
    f"color: {Palette.TEXT_PRIMARY}; }}"
)

_DEFAULT_ROUTE = "dashboard"


def _known_routes() -> frozenset[str]:
    """Every route a persisted `last_route` is allowed to name.

    @details A restored value is a request, not a command (`EPIC-010` design
    D5): a route from an older build that got renamed or removed must fall
    back to `_DEFAULT_ROUTE`, never navigate to something that no longer
    exists. Computed from the same `_NAV_SECTIONS`/`_BOTTOM_ACTIONS` that
    already are this module's one source of truth for what is navigable —
    not a second list that could drift from them.
    """
    routes: set[str] = set()
    for section in _NAV_SECTIONS:
        for item in section.items:
            if item.is_navigable and item.route:
                routes.add(item.route)
    for item in _BOTTOM_ACTIONS:
        if item.is_navigable and item.route:
            routes.add(item.route)
    return frozenset(routes)


_KNOWN_ROUTES = _known_routes()

#: This slice's flat keys. Named constants rather than inline literals so
#: `capture_state()` and `restore_state()` cannot drift from each other.
_GEOMETRY_KEY = "geometry_b64"
_ROUTE_KEY = "last_route"
_SIDEBAR_COLLAPSED_KEY = "sidebar_collapsed"


class MainWindow(QMainWindow):
    """
    @brief The application shell: navigation sidebar + screen router.

    @details
    Owns only assembly logic:
    - Creates the Sidebar component and wires sig_navigate → switch_screen.
    - Creates the PresenterManager (router) and registers all screens.
    - Routes switch_screen calls from Sidebar to the router and back.
    """

    def __init__(
        self,
        app_engine,
        *,
        state_coordinator: UiStateCoordinator | None = None,
    ) -> None:
        super().__init__()
        self._app = app_engine
        # Set before any geometry call: `resizeEvent`/`moveEvent` may fire
        # synchronously as a side effect of `resize()`/`restoreGeometry()`
        # below, and both call `_mark_dirty()`, which reads this attribute.
        self._state_coordinator = state_coordinator
        self._current_route = _DEFAULT_ROUTE

        self.setWindowTitle(_WINDOW_TITLE)
        self.resize(*_WINDOW_SIZE)

        # ---- Shell layout ------------------------------------------------
        central = QWidget()
        self.setCentralWidget(central)
        shell_layout = QHBoxLayout(central)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        # ---- Sidebar component -------------------------------------------
        self._sidebar = Sidebar(sections=_NAV_SECTIONS, bottom_actions=_BOTTOM_ACTIONS)
        self._sidebar.sig_navigate.connect(self.switch_screen)
        self._sidebar.collapsed_changed.connect(self._mark_dirty)

        # ---- Content area -----------------------------------------------
        self._stacked = QStackedWidget()
        self._stacked.setStyleSheet(_CONTENT_BG_STYLE)

        shell_layout.addWidget(self._sidebar)
        shell_layout.addWidget(self._stacked)

        # ---- Router setup -----------------------------------------------
        self._setup_router()

        # ---- Restore remembered state, then navigate ----------------------
        # `restore_state()` (below) only VALIDATES and stores the intended
        # route into `self._current_route` — it does not navigate itself, so
        # there is exactly one call to `switch_screen()` on boot regardless
        # of whether anything was restored.
        if self._state_coordinator is not None:
            self._state_coordinator.restore_into(self)
        self.switch_screen(self._current_route)

    def shutdown(self) -> None:
        """Requests cooperative presenter shutdown before engine teardown."""
        if self._state_coordinator is not None:
            # A pending debounced write does not fire once the event loop
            # stops turning — this is the real safety net, not the timer.
            self._state_coordinator.flush()
        self._router.shutdown()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.shutdown()
        super().closeEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._mark_dirty()

    def moveEvent(self, event: QMoveEvent) -> None:
        super().moveEvent(event)
        self._mark_dirty()

    # ------------------------------------------------------------------ #
    # IStateContributor — structural, no base class (EPIC-010C)
    # ------------------------------------------------------------------ #

    @property
    def state_scope(self) -> StateScope:
        return StateScope(key="shell")

    def capture_state(self) -> StateData:
        # `.data()` is typed as `bytes | bytearray | memoryview` in PySide6's
        # stubs (it is always plain `bytes` at runtime for a `QByteArray`);
        # wrapping in `bytes(...)` normalizes the type without changing the
        # value, since all three union members satisfy the buffer protocol.
        geometry_b64 = bytes(self.saveGeometry().toBase64().data()).decode("ascii")
        return {
            _GEOMETRY_KEY: geometry_b64,
            _ROUTE_KEY: self._current_route,
            _SIDEBAR_COLLAPSED_KEY: self._sidebar.is_collapsed,
        }

    def restore_state(self, data: StateData) -> None:
        """Applies a previously captured slice. See the class docstring for
        why this only validates and stores — it does not navigate."""
        geometry_b64 = data.get(_GEOMETRY_KEY)
        if isinstance(geometry_b64, str) and geometry_b64:
            blob = QByteArray.fromBase64(geometry_b64.encode("ascii"))
            self.restoreGeometry(blob)  # False return -> keeps the default size

        collapsed = data.get(_SIDEBAR_COLLAPSED_KEY)
        if isinstance(collapsed, bool):
            self._sidebar.set_collapsed(collapsed)

        route = data.get(_ROUTE_KEY)
        if isinstance(route, str) and route in _KNOWN_ROUTES:
            self._current_route = route

    def _mark_dirty(self) -> None:
        if self._state_coordinator is not None:
            self._state_coordinator.mark_dirty(self)

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
        # `build_backtest_view`, not `BackTestView()` (`EPIC-013F`): which
        # View this install uses is a named choice read from config, and the
        # factory's return type says what the router may do with it. Read
        # once, here — a View is never swapped while the app runs.
        config = self._app.context.container.resolve(IConfig)
        self._router.register(
            "backtest",
            BackTestPresenter,
            lambda: build_backtest_view(config),
        )

    def switch_screen(self, route_name: str) -> None:
        """
        @brief Navigate to a registered screen and sync the sidebar active state.
        @param route_name The route key registered with the PresenterManager.
        """
        self._router.navigate_to(route_name)
        self._sidebar.set_active(route_name)
        self._current_route = route_name
        self._mark_dirty()


# ---------------------------------------------------------------------------
# Legacy entry point — kept so that existing test imports from this module
# (test_sanity_ui_e2e.py) continue to work without modification.
# New code should use app_bootstrapper.main() instead.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from Sagittarius_Elite_Warrior.src.presentation.ui.app_bootstrapper import main

    main()
