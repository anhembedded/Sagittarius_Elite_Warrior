"""`EPIC-010C` — `MainWindow` remembers geometry and the sidebar's collapsed
state across a restart. It deliberately does NOT remember the active route
(`BUG-104`) — every boot always lands on the registered default screen; see
`main_window.py`'s own `BUG-104` docstring note for why.

Lives in `integration/`, not `unit/`: constructing a real `MainWindow` always
navigates to a real screen (`switch_screen()` runs unconditionally at the end
of `__init__`), which lazily constructs a real presenter through the real DI
container — there is no lighter-weight way to exercise this class's own
restore/capture logic. Uses this directory's existing `app_engine` fixture
(a real boot, mocked only at the dispatcher) rather than inventing a second
one.

@par Why this file has its own window harness instead of `conftest.py`'s
`main_window` fixture
That fixture has no way to pass `state_coordinator`. `_WindowHarness` below
re-applies its documented teardown sequence (cancel autostart and the
presenter cancellation tokens, drain background work, clean up chart cards,
close + deleteLater + drain the event loop) for windows this suite must
construct itself.

@par Why the harness waits on submitted futures rather than calling
`IThreadManager.shutdown(wait=True)`
`conftest.py`'s fixture drains by shutting the pool down, which is fine at
teardown but fatal here: `test_route_change_and_sidebar_toggle_survive_a_restart`
opens a *second* window in the same process, and a shut-down
`ThreadPoolExecutor` rejects every later `submit()`. `IThreadManager` has no
wait-for-idle verb (only `submit` and `shutdown`), so the harness wraps
`submit` to record each `Future` and blocks on exactly those.

That draining is not defensive padding — without it this suite **deadlocked**,
reproducibly, in longer runs. `DataManagementPresenter.shutdown()` cancels
only cooperatively (it sets a token flag and returns; see its own docstring),
so a `run_auto_discover` worker from window 1 was still mid-`dispatch` while
the main thread built window 2's `DataManagementView`. Both threads then
touched the same `MagicMock` dispatcher, whose child-mock creation mutates
shared state and is not thread-safe, and the process hung with the main
thread stuck in GC. The cooperative-only shutdown is pre-existing app
behaviour, not something `EPIC-010` introduced; this harness is what keeps
the two windows from overlapping.
"""

from __future__ import annotations

import concurrent.futures
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.components.sidebar import Sidebar
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
from Sagittarius_Elite_Warrior.tests.conftest import real_screen_registry
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

#: A drain that exceeds this is a hang, not slow work — every task these
#: windows submit runs against a mocked dispatcher and returns in
#: milliseconds. Bounded so a regression fails loudly instead of hanging the
#: suite, which is exactly how the deadlock above first presented itself.
_DRAIN_TIMEOUT_SECONDS = 30.0


def _coordinator_over(tmp_path: Path) -> UiStateCoordinator:
    """A real `ConfigManagerStateStore` over a scratch file — not
    `InMemoryStateStore` — because this suite is proving the whole path end
    to end, the same reasoning `test_config_manager_state_store.py`
    documents for promoting the feasibility probe into a permanent test."""
    locator = RepoStateStoreLocator(repo_root=tmp_path)
    store = ConfigManagerStateStore(locator)
    return UiStateCoordinator(store, debounce_ms=50_000)  # flush() drives writes


class _WindowHarness:
    """Opens `MainWindow`s and guarantees each one is fully quiet before the
    next is built (and before the test ends). See the module docstring."""

    def __init__(self, qtbot, app_engine, monkeypatch) -> None:
        self._qtbot = qtbot
        self._app_engine = app_engine
        self._open_windows: list[MainWindow] = []
        self._futures: list[concurrent.futures.Future] = []

        thread_manager = app_engine.context.container.resolve(IThreadManager)
        real_submit = thread_manager.submit

        def recording_submit(task, *args, **kwargs):
            future = real_submit(task, *args, **kwargs)
            self._futures.append(future)
            return future

        monkeypatch.setattr(thread_manager, "submit", recording_submit)

    def open(self, coordinator: UiStateCoordinator | None = None) -> MainWindow:
        registry = real_screen_registry(self._app_engine.context.container)
        window = MainWindow(
            self._app_engine,
            registry,
            sidebar_factory=Sidebar,
            state_coordinator=coordinator,
        )
        self._qtbot.addWidget(window)
        self._open_windows.append(window)
        return window

    def close(self, window: MainWindow) -> None:
        """Flushes state, cancels every background worker this window owns,
        then blocks until they have actually returned."""
        window.shutdown()  # flushes state_coordinator, disposes presenters

        for entry in window._router._registry.values():
            presenter = entry.get("presenter_instance")
            autostart = getattr(presenter, "_autostart", None)
            if autostart is not None:
                autostart.shutdown()
            token = getattr(presenter, "_cancellation_token", None)
            if token is not None:
                token.cancel()

        pending = self._futures
        self._futures = []
        _, not_done = concurrent.futures.wait(pending, timeout=_DRAIN_TIMEOUT_SECONDS)
        assert not not_done, (
            f"{len(not_done)} background task(s) still running "
            f"{_DRAIN_TIMEOUT_SECONDS}s after shutdown — see this module's "
            f"docstring, this is the deadlock condition, not slow work"
        )

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
        self._qtbot.wait(100)  # let the DeferredDelete actually be processed
        self._open_windows.remove(window)

    def close_all(self) -> None:
        for window in list(self._open_windows):
            self.close(window)


@pytest.fixture
def windows(qtbot, app_engine, monkeypatch):
    harness = _WindowHarness(qtbot, app_engine, monkeypatch)
    yield harness
    harness.close_all()


def test_a_bare_main_window_still_works_with_no_coordinator(windows):
    """Backward compatibility: every existing caller that omits
    `state_coordinator` — several tests, and every route in production
    before `010A`/`010B` are promoted to the Engine — must keep working
    exactly as before."""
    window = windows.open()

    assert window._current_route == "dashboard"


def test_restores_sidebar_and_geometry_but_never_the_route(windows, tmp_path):
    """`BUG-104`: a stored `last_route` from a prior session (even one still
    valid today) must never become the boot screen — only geometry and the
    sidebar's collapsed flag are cosmetic enough to restore verbatim."""
    coordinator = _coordinator_over(tmp_path)
    coordinator._store.write(
        StateScope(key="shell"),
        {"last_route": "backtest", "sidebar_collapsed": True},
    )

    window = windows.open(coordinator)

    assert window._current_route == "dashboard"
    assert window._sidebar.is_collapsed is True


def test_boot_never_constructs_a_non_default_screen_even_with_a_stored_route(
    windows, tmp_path
):
    """Proves the lazy-loading guarantee end to end, not just by reading
    `_current_route`: a stored `last_route` of `"trading"` must not make
    `PresenterManager` construct `TradingPresenter` at boot — it stays
    lazily un-built exactly as it would for a route nobody ever visited.
    This is the literal reported shape of `BUG-104`: `TradingPresenter.
    __init__` unconditionally starts a real `SyncMarketDataCommand`/
    `StartLiveStreamCommand` sequence (`EPIC-021I` — no separate Start
    step, by that screen's own documented design), so merely *constructing*
    it is the observable harm — a prior session leaving `"trading"` stored
    must never cause that construction to happen at boot."""
    coordinator = _coordinator_over(tmp_path)
    coordinator._store.write(StateScope(key="shell"), {"last_route": "trading"})

    window = windows.open(coordinator)

    dashboard_entry = window._router._registry["dashboard"]
    trading_entry = window._router._registry["trading"]
    assert dashboard_entry["presenter_instance"] is not None
    assert trading_entry["presenter_instance"] is None


def test_sidebar_toggle_survives_a_restart_but_the_route_resets_to_default(
    windows, tmp_path
):
    """The real round trip: change state, close the window completely, then
    reopen with a fresh store instance pointed at the same file — as a real
    restart would be. `BUG-104`: unlike the sidebar's collapsed flag, the
    route a user last navigated to must NOT come back on the next launch.

    `windows.close()` between the two is load-bearing, not tidiness: see the
    module docstring for the deadlock that skipping it produced.
    """
    coordinator = _coordinator_over(tmp_path)
    window = windows.open(coordinator)

    window.switch_screen("data_management")
    window._sidebar.set_collapsed(True)
    window._sidebar.collapsed_changed.emit()  # what the real toggle button fires
    windows.close(window)  # flushes, then waits for every worker to return

    reopened_coordinator = _coordinator_over(tmp_path)  # a fresh process, fresh store
    reopened = windows.open(reopened_coordinator)

    assert reopened._current_route == "dashboard"
    assert reopened._sidebar.is_collapsed is True


def test_capture_state_never_includes_the_route(windows, tmp_path):
    """`BUG-104`: the route is deliberately not part of this slice at all —
    not merely restored-and-ignored, never captured in the first place."""
    coordinator = _coordinator_over(tmp_path)
    window = windows.open(coordinator)
    window.switch_screen("backtest")
    captured = window.capture_state()

    assert "last_route" not in captured
    assert isinstance(captured["geometry_b64"], str) and captured["geometry_b64"]
    assert captured["sidebar_collapsed"] is window._sidebar.is_collapsed
