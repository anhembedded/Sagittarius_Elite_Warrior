"""`EPIC-010C` — `MainWindow` remembers geometry, the last route, and the
sidebar's collapsed state across a restart.

Lives in `integration/`, not `unit/`: constructing a real `MainWindow` always
navigates to a real screen (`switch_screen()` runs unconditionally at the end
of `__init__`), which lazily constructs a real presenter through the real DI
container — there is no lighter-weight way to exercise this class's own
restore/capture logic. Uses this directory's existing `app_engine` fixture
(a real boot, mocked only at the dispatcher) rather than inventing a second
one.

@par Why this file has its own `open_window` fixture instead of reusing
`conftest.py`'s `main_window` fixture
That fixture has no way to pass `state_coordinator`. But its long docstring
documents *why* it does more than `MainWindow(app_engine)` + `.close()`: a
background AutoStartController timer or thread-pool task left running past
a test's end can fire into already-torn-down Qt widgets — a real, previously
reproduced crash. `open_window` below re-applies that exact same safety
sequence (cancel autostart/cancellation token, drain the thread pool, clean
up chart cards, close + deleteLater + drain the event loop) so this suite
gets the same guarantee for windows it constructs directly.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import MainWindow
from Sagittarius_Elite_Warrior.src.presentation.ui.state.adapters.config_manager_state_store import (
    ConfigManagerStateStore,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.adapters.repo_state_store_locator import (
    RepoStateStoreLocator,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.state_scope import StateScope
from Sagittarius_Elite_Warrior.src.presentation.ui.state.ui_state_coordinator import (
    UiStateCoordinator,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager


def _coordinator_over(tmp_path: Path) -> UiStateCoordinator:
    """A real `ConfigManagerStateStore` over a scratch file — not
    `InMemoryStateStore` — because this suite is proving the whole path end
    to end, the same reasoning `test_config_manager_state_store.py`
    documents for promoting the feasibility probe into a permanent test."""
    locator = RepoStateStoreLocator(repo_root=tmp_path)
    store = ConfigManagerStateStore(locator)
    return UiStateCoordinator(store, debounce_ms=50_000)  # flush() drives writes


@pytest.fixture
def open_window(qtbot, app_engine):
    """Returns a factory `open_window(coordinator=None) -> MainWindow`.

    Every window it constructs is torn down the same way `conftest.py`'s
    `main_window` fixture tears down its own window — see the module
    docstring for why that matters.
    """
    windows: list[MainWindow] = []

    def _open(coordinator: UiStateCoordinator | None = None) -> MainWindow:
        window = MainWindow(app_engine, state_coordinator=coordinator)
        qtbot.addWidget(window)
        windows.append(window)
        return window

    yield _open

    for window in windows:
        window.shutdown()  # flushes state_coordinator, requests presenter shutdown
        for entry in window._router._registry.values():
            presenter = entry.get("presenter_instance")
            autostart = getattr(presenter, "_autostart", None)
            if autostart is not None:
                autostart.shutdown()
            token = getattr(presenter, "_cancellation_token", None)
            if token is not None:
                token.cancel()

    thread_manager = app_engine.context.container.resolve(IThreadManager)
    if thread_manager is not None:
        thread_manager.shutdown(wait=True)

    for window in windows:
        for entry in window._router._registry.values():
            view = entry.get("view_instance")
            cards = getattr(view, "chart_cards", None)
            if cards:
                for card in cards:
                    if hasattr(card, "cleanup"):
                        card.cleanup()
                cards.clear()
        window.close()
        window.deleteLater()

    qtbot.wait(100)


def test_a_bare_main_window_still_works_with_no_coordinator(open_window):
    """Backward compatibility: every existing caller that constructs
    `MainWindow(app_engine)` with no `state_coordinator` — several tests, and
    every route in production before `010A`/`010B` are promoted to the
    Engine — must keep working exactly as before."""
    window = open_window()

    assert window._current_route == "dashboard"


def test_restores_route_sidebar_and_geometry_from_a_prior_session(
    open_window, tmp_path
):
    coordinator = _coordinator_over(tmp_path)
    coordinator._store.write(
        StateScope(key="shell"),
        {"last_route": "backtest", "sidebar_collapsed": True},
    )

    window = open_window(coordinator)

    assert window._current_route == "backtest"
    assert window._sidebar.is_collapsed is True


def test_an_unknown_persisted_route_falls_back_to_the_default(open_window, tmp_path):
    """D5 — a restored value is a request, not a command: a route from an
    older build that got renamed or removed must not be navigated to."""
    coordinator = _coordinator_over(tmp_path)
    coordinator._store.write(
        StateScope(key="shell"), {"last_route": "a_screen_that_no_longer_exists"}
    )

    window = open_window(coordinator)

    assert window._current_route == "dashboard"


def test_restoring_a_non_default_route_never_touches_the_default_screen(
    open_window, tmp_path
):
    """Proves the lazy-loading guarantee end to end, not just by reading
    `_current_route`: restoring straight into `"backtest"` must mean
    `PresenterManager` never constructs the Dev Board presenter at all —
    it stays lazily un-built exactly as it would for a route nobody ever
    visited."""
    coordinator = _coordinator_over(tmp_path)
    coordinator._store.write(StateScope(key="shell"), {"last_route": "backtest"})

    window = open_window(coordinator)

    dashboard_entry = window._router._registry["dashboard"]
    backtest_entry = window._router._registry["backtest"]
    assert dashboard_entry["presenter_instance"] is None
    assert backtest_entry["presenter_instance"] is not None


def test_route_change_and_sidebar_toggle_survive_a_restart(open_window, tmp_path):
    """The real round trip: change state, flush, reopen with a fresh store
    instance pointed at the same file — as a real restart would be."""
    coordinator = _coordinator_over(tmp_path)
    window = open_window(coordinator)

    window.switch_screen("data_management")
    window._sidebar.set_collapsed(True)
    window._sidebar.collapsed_changed.emit()  # what the real toggle button fires
    window.shutdown()  # flushes now, rather than waiting for open_window's teardown

    reopened_coordinator = _coordinator_over(tmp_path)  # a fresh process, fresh store
    reopened = open_window(reopened_coordinator)

    assert reopened._current_route == "data_management"
    assert reopened._sidebar.is_collapsed is True


def test_capture_state_round_trips_through_restore_state(open_window, tmp_path):
    coordinator = _coordinator_over(tmp_path)
    window = open_window(coordinator)
    window.switch_screen("backtest")
    captured = window.capture_state()

    assert captured["last_route"] == "backtest"
    assert isinstance(captured["geometry_b64"], str) and captured["geometry_b64"]
    assert captured["sidebar_collapsed"] is window._sidebar.is_collapsed
