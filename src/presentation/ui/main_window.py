"""
@brief MainWindow — the application shell and screen router.

@details
Single responsibility: assemble the Sidebar, QStackedWidget, and
PresenterManager, then wire navigation signals between them.

`EPIC-016` — this shell knows no concrete screen. It depends on
`IScreenRegistry` (which screens exist, and how the sidebar is structured)
and `ISidebar` (how to talk to whatever navigation widget the caller
supplies) — both injected. Assembling the registry, registering the 4 real
`*ScreenModule`s, and choosing the concrete `Sidebar` factory all happen in
`app_bootstrapper.py`, the composition root; adding a 5th screen never
requires touching this file.

Engine boot, QApplication setup, and theming live in app_bootstrapper.py.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import QByteArray
from PySide6.QtGui import QCloseEvent, QMoveEvent, QResizeEvent
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QStackedWidget, QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette
from Sagittarius_Elite_Warrior.src.presentation.ui.components.sidebar import (
    ISidebar,
    NavItem,
    NavSection,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.registry import IScreenRegistry
from Sagittarius_Elite_Warrior.src.presentation.ui.state.state_scope import (
    StateData,
    StateScope,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.ui_state_coordinator import (
    UiStateCoordinator,
)
from sagittarius_engine.extensions.pyside_mvc import PresenterManager

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

#: This slice's flat keys. Named constants rather than inline literals so
#: `capture_state()` and `restore_state()` cannot drift from each other.
_GEOMETRY_KEY = "geometry_b64"
_SIDEBAR_COLLAPSED_KEY = "sidebar_collapsed"


class MainWindow(QMainWindow):
    """
    @brief The application shell: navigation sidebar + screen router.

    @details
    Owns only assembly logic:
    - Creates the sidebar via `sidebar_factory` and wires sig_navigate → switch_screen.
    - Creates the PresenterManager (router) and binds every screen `screen_registry` knows.
    - Routes switch_screen calls from the sidebar to the router and back.

    @par EPIC-010C — remembered shell state
    `MainWindow` itself implements `IStateContributor` (structurally — it is a
    `typing.Protocol`, so no base class or import-time coupling is needed) rather
    than delegating to a helper object: window geometry and the sidebar's
    collapsed flag are `MainWindow`'s own fields, and `code-quality-rule.md`'s
    Single-Scope Cohesion says a state that is this tightly coupled to one
    object's own lifecycle belongs in that object, not split across a second
    file. Window geometry is persisted as the real `QByteArray`
    `saveGeometry()`/`restoreGeometry()` produce, base64-encoded —
    `restoreGeometry()` already performs its own off-screen and DPI sanity
    checks, so a hand-rolled `x/y/w/h` would buy no extra safety while getting
    multi-monitor wrong in ways Qt already handles (`EPIC-010` design §5.6.3).
    `state_coordinator` is optional and defaults to `None`: this app has no DI
    container wiring for it yet (`010A`/`010B` are Elite-only, not yet promoted
    to the Engine), and every existing caller that constructs a bare
    `MainWindow(app_engine, screen_registry, sidebar_factory)` — several tests —
    must keep working unchanged.

    @par BUG-104 — the active route is deliberately NOT remembered
    `EPIC-010C` originally also persisted `last_route` and navigated straight
    into it on boot. That silently combined with screens whose own design is
    "being open means live" (`TradingPresenter` — `EPIC-021I`: opening it
    unconditionally dispatches `SyncMarketDataCommand`/`StartLiveStreamCommand`,
    no separate Start step, by its own documented intent) to make **launching
    the app** — no click, no user action at all — start a real network stream
    whenever the user's previous session had happened to end on that screen.
    Every boot must land on the registered default route, full stop; a
    screen's own "open = go live" behaviour then only ever fires from an
    actual user click on the sidebar.
    """

    def __init__(
        self,
        app_engine,
        screen_registry: IScreenRegistry,
        sidebar_factory: Callable[[Sequence[NavSection], Sequence[NavItem]], ISidebar],
        *,
        state_coordinator: UiStateCoordinator | None = None,
    ) -> None:
        super().__init__()
        self._app = app_engine
        # Set before any geometry call: `resizeEvent`/`moveEvent` may fire
        # synchronously as a side effect of `resize()`/`restoreGeometry()`
        # below, and both call `_mark_dirty()`, which reads this attribute.
        self._state_coordinator = state_coordinator
        self._current_route = screen_registry.get_default_route()

        self.setWindowTitle(_WINDOW_TITLE)
        self.resize(*_WINDOW_SIZE)

        # ---- Shell layout ------------------------------------------------
        central = QWidget()
        self.setCentralWidget(central)
        shell_layout = QHBoxLayout(central)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        # ---- Sidebar component --------------------------------------------
        nav_sections, bottom_actions = screen_registry.build_sidebar_navigation()
        self._sidebar: ISidebar = sidebar_factory(nav_sections, bottom_actions)
        self._sidebar.sig_navigate.connect(self.switch_screen)
        self._sidebar.collapsed_changed.connect(self._mark_dirty)

        # ---- Content area -----------------------------------------------
        self._stacked = QStackedWidget()
        self._stacked.setStyleSheet(_CONTENT_BG_STYLE)

        shell_layout.addWidget(self._sidebar)
        shell_layout.addWidget(self._stacked)

        # ---- Router setup -----------------------------------------------
        self._router = PresenterManager(self._app.context.container, self._stacked)
        screen_registry.bind_to_router(self._router)

        # ---- Restore remembered state, then navigate ----------------------
        # `restore_state()` (below) applies geometry/sidebar only — never the
        # route (`BUG-104`) — so `self._current_route` is still exactly
        # `get_default_route()` set above, and this is always the one and
        # only `switch_screen()` call on boot, always into the default
        # screen, regardless of what the previous session had open.
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
            _SIDEBAR_COLLAPSED_KEY: self._sidebar.is_collapsed,
        }

    def restore_state(self, data: StateData) -> None:
        """Applies a previously captured slice. See the class docstring's
        `BUG-104` note for why the active route is deliberately never
        restored here — geometry and the sidebar's collapsed flag are pure
        cosmetics with no side effect from being applied; which screen boots
        active is not."""
        geometry_b64 = data.get(_GEOMETRY_KEY)
        if isinstance(geometry_b64, str) and geometry_b64:
            blob = QByteArray.fromBase64(geometry_b64.encode("ascii"))
            self.restoreGeometry(blob)  # False return -> keeps the default size

        collapsed = data.get(_SIDEBAR_COLLAPSED_KEY)
        if isinstance(collapsed, bool):
            self._sidebar.set_collapsed(collapsed)

    def _mark_dirty(self) -> None:
        if self._state_coordinator is not None:
            self._state_coordinator.mark_dirty(self)

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
