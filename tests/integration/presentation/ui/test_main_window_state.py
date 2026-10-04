"""`EPIC-033C` — the workbench window remembers its geometry, its last mode
and each mode's layout across a restart, and a restore at start never makes a
mode go live (`BUG-104`).

`BUG-104` was the window restoring the Trading screen, whose presenter
started a sync and a live stream in its constructor. The window now builds
every mode at start (the user's decision, 2026-10-04), so the guarantee moved
from "a remembered screen is never built" to "a remembered mode is shown as a
`RESTORE`, and nothing goes live on a restore that needs a click": the Dev
Board's opt-in auto-start (enabled in this directory's config) is the probe.

Lives in `integration/`: building a real `MainWindow` builds every real
screen through the real DI container. Uses this directory's `app_engine`
fixture (a real boot, mocked only at the dispatcher).

@par Why this file has its own window harness instead of `conftest.py`'s
`main_window` fixture
That fixture has no way to pass `state_coordinator`. `_WindowHarness` below
re-applies its documented teardown sequence (cancel autostart and the
presenter cancellation tokens, drain background work, clean up chart cards,
close + deleteLater + drain the event loop) for windows this suite must
construct itself.

@par Why the harness waits on submitted futures rather than calling
`IThreadManager.shutdown(wait=True)`
A restart opens a *second* window in the same process, and a shut-down
`ThreadPoolExecutor` rejects every later `submit()`. `IThreadManager` has no
wait-for-idle verb, so the harness wraps `submit` to record each `Future`
and blocks on exactly those. Without that draining this suite deadlocked:
a `run_auto_discover` worker from window 1 was still mid-`dispatch` on the
shared `MagicMock` dispatcher while the main thread built window 2."""

from __future__ import annotations

import concurrent.futures
from pathlib import Path

import pytest
from PySide6.QtWidgets import QDockWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import MainWindow
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.adapters.config_manager_state_store import (
    ConfigManagerStateStore,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.adapters.repo_state_store_locator import (
    RepoStateStoreLocator,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.state_scope import StateScope
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.ui_state_coordinator import (
    UiStateCoordinator,
)
from Sagittarius_Elite_Warrior.tests.conftest import real_screen_registry
from sagittarius_engine.extensions.pyside_mvc.workbench.navigation_service import (
    NavigationSource as ShellNavigationSource,
)
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
        window = MainWindow(self._app_engine, registry, state_coordinator=coordinator)
        self._qtbot.addWidget(window)
        self._open_windows.append(window)
        return window

    def close(self, window: MainWindow) -> None:
        """Flushes state, cancels every background worker this window owns,
        then blocks until they have actually returned."""
        window.shutdown()  # flushes state_coordinator, disposes presenters

        for presenter in window.presenters.values():
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

        for host in window.hosts.values():
            cards = getattr(host.view, "chart_cards", None)
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


def _autostart_has_begun(window: MainWindow) -> bool:
    autostart = window.presenters["dashboard"]._autostart
    assert autostart is not None, "this directory's config enables the auto-start"
    return autostart.has_begun


def test_a_window_with_no_coordinator_opens_the_default_mode(windows):
    window = windows.open()

    assert window.current_mode == "trading.futures"
    assert window.last_source is ShellNavigationSource.RESTORE


def test_a_remembered_mode_comes_back_as_a_restore_and_does_not_go_live(
    windows, tmp_path
):
    """`BUG-104`: the Dev Board comes back, and its auto-start does not run:
    nobody clicked."""
    coordinator = _coordinator_over(tmp_path)
    coordinator._store.write(StateScope(key="shell"), {"mode": "dashboard"})

    window = windows.open(coordinator)

    assert window.current_mode == "dashboard"
    assert window.last_source is ShellNavigationSource.RESTORE
    assert _autostart_has_begun(window) is False


def test_a_click_on_the_dev_board_begins_its_auto_start(windows):
    """The positive half: the same auto-start does run on a user's open."""
    window = windows.open()

    window.switch_screen("dashboard")

    assert _autostart_has_begun(window) is True


def test_a_mode_retired_since_the_last_session_opens_the_default(windows, tmp_path):
    """`"trading"` is what a session from before `EPIC-028M` left stored."""
    coordinator = _coordinator_over(tmp_path)
    coordinator._store.write(StateScope(key="shell"), {"mode": "trading"})

    window = windows.open(coordinator)

    assert window.current_mode == "trading.futures"


def test_the_last_mode_and_a_closed_panel_survive_a_restart(windows, tmp_path):
    """The real round trip: change state, close the window completely, then
    reopen with a fresh store over the same file, as a restart would.

    `windows.close()` between the two is load-bearing: see the module
    docstring for the deadlock skipping it produced."""
    coordinator = _coordinator_over(tmp_path)
    window = windows.open(coordinator)
    window.switch_screen("dashboard")
    docks = window.hosts["dashboard"].view.surface.findChildren(QDockWidget)
    assert docks, "the Dev Board's surface has panels"
    closed = docks[0].objectName()
    docks[0].close()
    window.switch_screen("data_management")
    windows.close(window)  # flushes, then waits for every worker to return

    reopened = windows.open(_coordinator_over(tmp_path))

    assert reopened.current_mode == "data_management"
    dock = reopened.hosts["dashboard"].view.surface.findChild(QDockWidget, closed)
    assert dock is not None
    assert dock.isHidden()
