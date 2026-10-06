"""`EPIC-033C` — the workbench window remembers its geometry, its last mode
and each mode's layout across a restart, and a restore at start never makes a
mode go live (`BUG-104`).

`BUG-104` was the window restoring the Trading screen, whose presenter
started a sync and a live stream in its constructor. The window now builds
every mode at start (the user's decision, 2026-10-04), so the guarantee moved
from "a remembered screen is never built" to "a remembered mode is shown as a
`RESTORE`, and nothing goes live on a restore that needs a click": the
Market mode's Watchlist stream, which starts on the user's open only, is the
probe (the Dev Board's opt-in auto-start was, until `EPIC-033P` deleted it).

Lives in `integration/`: building a real `MainWindow` builds every real
screen through the real DI container. Uses this directory's `app_engine`
fixture (a real boot, mocked only at the dispatcher).

@par Why this file has its own window harness instead of `conftest.py`'s
`main_window` fixture
That fixture has no way to pass `state_coordinator`. `_WindowHarness` below
re-applies its documented teardown sequence (drain background work, clean
up chart cards, close + deleteLater + drain the event loop) for windows this
suite must construct itself.

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
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.start_live_stream.command import (
    StartLiveStreamCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_presenter import (
    WATCHLIST_STREAM_OWNER,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_screen import (
    MARKET_ROUTE,
)
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
from Sagittarius_Elite_Warrior.tests.conftest import real_main_window
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_layout_checks import (
    rearrange,
    restart_problems,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.navigation_service import (
    NavigationSource as ShellNavigationSource,
)
from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
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
        window = real_main_window(self._app_engine, state_coordinator=coordinator)
        # Not handed to `qtbot.addWidget`: `close()` below closes and deletes
        # each window itself, and qtbot closing it again would find the C++
        # object gone while the test still holds the window.
        self._open_windows.append(window)
        return window

    def close(self, window: MainWindow) -> None:
        """Flushes state, disposes every presenter, then blocks until each
        background worker this window started has actually returned."""
        window.shutdown()  # flushes state_coordinator, disposes presenters

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


def _watchlist_streams(market_stream) -> bool:
    """Has the Market mode's Watchlist stream been started?"""
    return ("start", WATCHLIST_STREAM_OWNER) in market_stream.calls


def test_a_window_with_no_coordinator_opens_the_default_mode(windows):
    window = windows.open()

    assert window.current_mode == "trade"
    assert window.last_source is ShellNavigationSource.RESTORE


_EVERY_MODE = (
    "market",
    "trade",
    "bots",
    "data_management",
    "backtest",
)


@pytest.mark.parametrize("stored_mode", _EVERY_MODE)
def test_no_remembered_mode_opens_a_live_stream_at_launch(
    windows, tmp_path, market_stream, app_engine, monkeypatch, stored_mode
):
    """`BUG-104`, the reported path, for every mode: whichever mode the last
    session ended in, launching opens no market stream and dispatches no
    `StartLiveStreamCommand`. Every mode is built at start (`EPIC-033C`), so
    this covers each screen's constructor and its restore-time show."""
    dispatched: list[type] = []
    dispatcher = app_engine.context.container.resolve(IDispatcher)
    real_dispatch = dispatcher.dispatch

    def recording_dispatch(command_type, command):
        dispatched.append(command_type)
        return real_dispatch(command_type, command)

    monkeypatch.setattr(dispatcher, "dispatch", recording_dispatch)
    coordinator = _coordinator_over(tmp_path)
    coordinator._store.write(StateScope(key="shell"), {"mode": stored_mode})

    window = windows.open(coordinator)

    assert window.current_mode == stored_mode
    assert [call for call in market_stream.calls if call[0] == "start"] == []
    assert StartLiveStreamCommand not in dispatched


def test_every_mode_is_covered_by_the_launch_check(windows):
    """The list above is the window's own, so a new mode is not missed."""
    assert set(windows.open().navigation.modes()) == set(_EVERY_MODE)


def test_a_remembered_mode_comes_back_as_a_restore_and_does_not_go_live(
    windows, tmp_path, market_stream
):
    """`BUG-104`: the Market mode comes back, and its Watchlist does not
    start streaming: nobody clicked."""
    coordinator = _coordinator_over(tmp_path)
    coordinator._store.write(StateScope(key="shell"), {"mode": MARKET_ROUTE})

    window = windows.open(coordinator)

    assert window.current_mode == MARKET_ROUTE
    assert window.last_source is ShellNavigationSource.RESTORE
    assert _watchlist_streams(market_stream) is False


def test_a_click_on_the_market_mode_starts_its_watchlist_stream(windows, market_stream):
    """The positive half, re-homed from the Dev Board's auto-start
    (`EPIC-033P`): the same mode does go live on a user's open."""
    window = windows.open()
    assert _watchlist_streams(market_stream) is False

    window.switch_screen(MARKET_ROUTE)

    assert _watchlist_streams(market_stream) is True


@pytest.mark.parametrize("retired", ["trading", "trading.futures", "trading.spot"])
def test_a_mode_retired_since_the_last_session_opens_the_default(
    windows, tmp_path, retired
):
    """`"trading"` is what a session from before `EPIC-028M` left stored;
    a desk's route, what one from before `EPIC-033I` left."""
    coordinator = _coordinator_over(tmp_path)
    coordinator._store.write(StateScope(key="shell"), {"mode": retired})

    window = windows.open(coordinator)

    assert window.current_mode == "trade"


def test_the_last_mode_and_a_closed_panel_survive_a_restart(windows, tmp_path):
    """The real round trip: change state, close the window completely, then
    reopen with a fresh store over the same file, as a restart would.

    `windows.close()` between the two is load-bearing: see the module
    docstring for the deadlock skipping it produced."""
    coordinator = _coordinator_over(tmp_path)
    window = windows.open(coordinator)
    window.switch_screen(MARKET_ROUTE)
    docks = window.hosts[MARKET_ROUTE].findChildren(QDockWidget)
    assert docks, "the Market mode has panels"
    closed = docks[0].objectName()
    docks[0].close()
    window.switch_screen("data_management")
    windows.close(window)  # flushes, then waits for every worker to return

    reopened = windows.open(_coordinator_over(tmp_path))

    assert reopened.current_mode == "data_management"
    dock = reopened.hosts[MARKET_ROUTE].findChild(QDockWidget, closed)
    assert dock is not None
    assert dock.isHidden()


def test_every_modes_rearranged_layout_survives_a_restart(windows, tmp_path):
    """`ui-presentation-rule.md` §8, the restart half the conformance suite
    cannot run on its shared window: every mode is rearranged (each dock and
    toolbar moved, every other one hidden), the window closes, and a second
    window over the same file shows each mode as it was left. It found the
    commands toolbar of every mode with a surface back on top and shown,
    because only the surface's layout was saved (`ModeHost.remembered_hosts`)."""
    window = windows.open(_coordinator_over(tmp_path))
    closed_with = {}
    for route in window.navigation.modes():
        window.switch_screen(route)
        closed_with[route] = rearrange(window.hosts[route])
    windows.close(window)

    reopened = windows.open(_coordinator_over(tmp_path))

    problems = []
    for route, layout in closed_with.items():
        reopened.switch_screen(route)
        assert layout, f"{route} lays out no dock or toolbar to rearrange"
        problems += [
            f"{route}: {line}"
            for line in restart_problems(layout, reopened.hosts[route])
        ]
    assert not problems, "\n".join(problems)
