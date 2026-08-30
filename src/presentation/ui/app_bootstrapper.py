"""
@brief Application entry-point bootstrapper.

@details
Responsible for:
- Booting the Sagittarius Engine (config + create_app).
- Initialising QApplication (font, theme, exception handler, signal handler).
- Initialising UIWatchdog for main-thread freeze detection.
- Creating and showing MainWindow.
- Shutting down the Engine and background diagnostics on exit.

`main()` is deliberately split into `build()` / `teardown()`, with `main()`
itself reduced to `build() -> app.exec() -> teardown()`. This is not a
refactor for its own sake — it is `EPIC-009`'s D2: the Sanity tier needs to
launch this exact application, not a bespoke re-composition of it, and the
only way to do that without duplicating every line above is to give the real
entry point two callable halves instead of one monolithic function that also
owns the event loop.

`--self-check` is the smallest real consumer of that split (`EPIC-009`'s D2b,
degenerate case): boots the application for real, lets the event loop turn
once, then exits with a real process exit code — proving the app can start
and stop cleanly, out of process, the one thing no in-process test can prove
(see `tests/sanity/test_composition_root.py`'s own note on why
`threading.enumerate()` is only a proxy for a process actually dying). It is
not the general control channel D2b also describes (publish an event,
dispatch a command from outside the process) — that protocol is still
`Proposed` and gated on open questions in the ADR, several of them
security-relevant for an application holding exchange API credentials. Do not
extend `--self-check` into that protocol without resolving those first; see
`Tasks/epics/EPIC-009_sanity_tier_redesign/`.

`MainWindow` itself stays a pure assembly component with no Engine-boot side
effects.
"""

from __future__ import annotations

import os
import sys
import threading
import traceback
from dataclasses import dataclass

import qdarktheme
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.main import create_app
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette
from Sagittarius_Elite_Warrior.src.presentation.ui.common.qt_platform import (
    is_headless_qt_platform,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components import (
    CriticalErrorDialog,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.timeframe_pin_preferences import (
    TimeframePinPreferences,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.symbol_picker import (
    SymbolPreferences,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import MainWindow
from Sagittarius_Elite_Warrior.src.presentation.ui.state.adapters.config_manager_state_store import (
    ConfigManagerStateStore,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.adapters.repo_state_store_locator import (
    RepoStateStoreLocator,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.ui_state_coordinator import (
    UiStateCoordinator,
)
from sagittarius_engine import App
from sagittarius_engine.extensions.pyside_mvc import (
    UIWatchdog,
    get_theme_bridge,
    setup_qt_signal_handling,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.infrastructure.logging.dev_verbosity import (
    resolve_dev_verbosity,
)
from sagittarius_engine.interfaces.i_config import IConfig

#: `python -m ...app_bootstrapper --self-check`: boot for real, let the event
#: loop turn once, exit with a real process exit code. See the module
#: docstring for what this is and — just as importantly — what it is not.
_SELF_CHECK_FLAG = "--self-check"

# ---------------------------------------------------------------------------
# Config file paths — resolved relative to this file's location
# ---------------------------------------------------------------------------
_CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config"
)
_APP_CONFIG = os.path.join(_CONFIG_DIR, "app_config.json")
_USER_CONFIG = os.path.join(_CONFIG_DIR, "user_config.json")


#: Kept out of the repo root so a dev session never dirties `git status`;
#: `logs/` is git-ignored.
_LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "logs",
)


@dataclass
class AppRuntime:
    """Everything `build()` constructs that `teardown()` needs back.

    Not a general-purpose context object — it holds exactly the five handles
    `main()` used to keep as locals between assembly and shutdown, named the
    same as they always were. `app.exec()` deliberately stays outside both
    functions: it belongs to whichever caller decides how the event loop
    ends (waiting for the user to close the window, or `--self-check`'s
    single scheduled `quit()`), not to bootstrapping or to teardown.
    """

    app_engine: App
    app: QApplication
    window: MainWindow
    watchdog: UIWatchdog
    sig_timer: object


def build() -> AppRuntime:
    """Boots the Engine, then the UI, up to and NOT including `app.exec()`.

    Every step production runs before the event loop starts — real config,
    real DI container, real QApplication, real theme, real MainWindow. The
    only thing a caller can vary is what happens after this returns: run the
    event loop until the user closes the window (`main()`), or until one
    scheduled `quit()` fires (`--self-check`, and `EPIC-009`'s Sanity tier).
    Neither caller may skip a step here or substitute a piece of it — the
    instant they do, they are proving a different application, which is
    exactly what made the three `scripts/shutdown_*_probe.py` scripts drift
    from their real interfaces (`BUG-026`, `BUG-027`).
    """
    # ------------------------------------------------------------------ #
    # 1. Boot the Sagittarius Engine
    # ------------------------------------------------------------------ #
    config_manager = ConfigManager()
    config_manager.load_json(_APP_CONFIG)
    config_manager.load_json(_USER_CONFIG, writable=True)

    # The --dev/--debug -> log level/file mapping is generic engine behavior
    # (see sagittarius_engine.infrastructure.logging.dev_verbosity); what
    # else dev/debug mode turns on here is this app's own concern —
    # ConfigKeys.DEV_MODE (button-click auto-logging, per BaseView).
    verbosity = resolve_dev_verbosity(sys.argv, _LOG_DIR)
    if verbosity is not None:
        config_manager.load_dict(
            {
                ConfigKeys.DEV_MODE.value: True,
                "log.level": verbosity.log_level,
                "log.file": verbosity.log_file,
            }
        )
        print(
            f"{'Debug' if verbosity.is_debug else 'Dev'} mode enabled — log "
            f"level {verbosity.log_level}, full session written to "
            f"{verbosity.log_file} (attach this file to bug reports)."
        )

    app_engine = create_app(config_manager)
    app_engine.boot()

    # ------------------------------------------------------------------ #
    # 2. Boot PySide6 QApplication & Diagnostics
    # ------------------------------------------------------------------ #
    os.environ.setdefault(
        "QT_LOGGING_RULES", "qt.qpa.fonts.warning=false;qt.qpa.window=false"
    )
    app = QApplication(sys.argv)

    _install_exception_handler(app_engine)
    sig_timer = setup_qt_signal_handling(app)
    _apply_font(app, config_manager)
    _apply_theme(app, config_manager)
    # EPIC-006F: no QML left in this app at all (the last consumer, the
    # native chart, was deleted outright) — pyside_mvc.widgets' apply_role()
    # is the only remaining reader of get_theme_bridge(), populated
    # directly instead of as a side effect of configure_app_qml() (which no
    # longer needs calling here).
    get_theme_bridge(Palette.as_ui_dict())

    # ------------------------------------------------------------------ #
    # 3. Create and show MainWindow
    # ------------------------------------------------------------------ #
    # EPIC-010 — remembered UI state. Constructed here, after QApplication
    # exists, because UiStateCoordinator owns a QTimer. Nothing else needs a
    # handle on it: MainWindow.shutdown() flushes it, and teardown() already
    # calls that, so it stays out of AppRuntime.
    state_coordinator = UiStateCoordinator(
        ConfigManagerStateStore(RepoStateStoreLocator())
    )
    # Registered so screen presenters can find it: PresenterManager builds
    # each presenter as `presenter_class(view, container)`, with no seam for
    # extra constructor arguments, so the container is the only way through.
    # A presenter must therefore treat it as optional (see
    # DashboardPresenter) — every test that builds a presenter against a bare
    # container would otherwise break.
    app_engine.context.container.singleton(UiStateCoordinator, state_coordinator)

    # EPIC-014 — starred and recently used trading pairs, ONE store shared by
    # every screen that picks a symbol. Registered rather than owned by a
    # screen because that is what makes it shared: a star set on Backtest is
    # the same star Dev Board shows, which is the whole reason favourites are
    # worth having across a 1,400-entry list.
    #
    # Restored before the first screen is built, and marked dirty on every
    # mutation so the coordinator's debounce writes it — the same two calls
    # every other contributor makes, just made here because this one has no
    # presenter of its own.
    symbol_preferences = SymbolPreferences()
    state_coordinator.restore_into(symbol_preferences)
    symbol_preferences.set_on_changed(
        lambda: state_coordinator.mark_dirty(symbol_preferences)
    )
    app_engine.context.container.singleton(SymbolPreferences, symbol_preferences)

    # Follow-up to `EPIC-015` Phase 4 — pinned timeframes per chart, keyed by
    # symbol, shared by every `ChartToolbar` in the app the same way
    # `SymbolPreferences` is shared above: Backtest's single chart and each
    # of Dev Board's per-symbol charts read the same store, scoped by their
    # own symbol, so a Dev Board rebuild-on-symbol-change recovers the same
    # pinned set for a symbol it has already seen instead of resetting it.
    timeframe_pin_preferences = TimeframePinPreferences()
    state_coordinator.restore_into(timeframe_pin_preferences)
    timeframe_pin_preferences.set_on_changed(
        lambda: state_coordinator.mark_dirty(timeframe_pin_preferences)
    )
    app_engine.context.container.singleton(
        TimeframePinPreferences, timeframe_pin_preferences
    )
    window = MainWindow(app_engine, state_coordinator=state_coordinator)
    window.show()

    # Start UI Watchdog to monitor main-thread responsiveness during runtime
    engine_logger = (
        app_engine.context.logger
        if hasattr(app_engine, "context") and hasattr(app_engine.context, "logger")
        else None
    )
    watchdog = UIWatchdog(logger=engine_logger)
    watchdog.start()

    # Schedule readiness confirmation on the first event loop tick
    QTimer.singleShot(0, lambda: _log_ui_ready(app_engine))

    return AppRuntime(
        app_engine=app_engine,
        app=app,
        window=window,
        watchdog=watchdog,
        sig_timer=sig_timer,
    )


def teardown(runtime: AppRuntime) -> None:
    """Production's real shutdown path — window, watchdog, signal timer,
    engine, in that order. Every caller of `build()` must call this exactly
    once, whatever stopped the event loop.

    This is the half of the lifecycle no test tier used to reach at all:
    `tests/sanity/`'s old fixtures called `app.stop()` in teardown with no
    assertion, so a hang surfaced as a hung test run, not a failure. Three
    filed bugs — `BUG-007`, `BUG-023`, `BUG-041`, two of them P1 — were all
    found by a person watching a real process refuse to exit. Calling this
    from a real subprocess (`--self-check`, or a `subprocess.run(...)`-based
    sanity test) is the only way to prove that class of defect for real: a
    non-daemon thread surviving `teardown()` keeps the *process* alive, which
    `threading.enumerate()` inside pytest can only approximate.
    """
    runtime.window.shutdown()
    runtime.watchdog.stop()
    runtime.sig_timer.stop()
    runtime.app_engine.stop()
    _log_surviving_non_daemon_threads(runtime.app_engine)


def main() -> None:
    """Application entry point — boot Engine, boot UI, run event loop, shutdown.

    `--self-check` (see the module docstring) schedules its own exit instead
    of waiting on the window; every other line of the real application still
    runs unchanged.
    """
    runtime = build()

    if _SELF_CHECK_FLAG in sys.argv:
        QTimer.singleShot(0, runtime.app.quit)

    exit_code = runtime.app.exec()
    teardown(runtime)
    sys.exit(exit_code)


# ------------------------------------------------------------------ #
# Private helpers — each owns exactly one bootstrap concern
# ------------------------------------------------------------------ #


def _log_ui_ready(app_engine) -> None:
    """Log readiness confirmation when the main window is rendered and event loop is active."""
    ready_msg = "UI Layer Ready — MainWindow rendered and Qt event loop active."
    if hasattr(app_engine, "context") and hasattr(app_engine.context, "logger"):
        app_engine.context.logger.info(ready_msg)
    else:
        print(ready_msg)


_STACK_FRAME_LIMIT = 12


def _format_thread_stack(thread: threading.Thread) -> str:
    """The stack a surviving thread is stuck in, not just its name.

    `BUG-059`'s blocker is precisely this gap: the diagnostic already named
    the survivor, but `'ThreadPoolExecutor-3_0'` does not say what it is
    *running*, and that report's open question is "which task". A thread
    name is assigned by the pool, so every task that pool ever ran shares
    it. The stack is the only thing that distinguishes them.

    `sys._current_frames()` reads other threads' frames without stopping
    them — the same technique that identified the integration-suite
    deadlock earlier (there via `faulthandler` on SIGABRT, which is not
    available here because the process is not wedged yet).

    Deliberately bounded to the innermost `_STACK_FRAME_LIMIT` frames: the
    blocking call is at the bottom, and an unbounded dump of every worker
    would bury it. A thread blocked inside a C call has no Python frame at
    all, which is itself the answer, so it is reported rather than skipped.
    """
    frame = sys._current_frames().get(thread.ident or -1)
    if frame is None:
        return f"    {thread.name!r}: no Python frame (blocked in a C call?)"
    body = "".join(traceback.format_stack(frame)[-_STACK_FRAME_LIMIT:]).rstrip()
    return f"    {thread.name!r} is stuck at:\n{body}"


def _log_surviving_non_daemon_threads(app_engine) -> None:
    """BUG-052 — `app_engine.stop()` returning is not the same as the process
    being able to exit. `IThreadManager`'s pool is a `ThreadPoolExecutor`
    (`sagittarius_engine`'s `ThreadManagerExtension.shutdown()` calls it with
    `wait=False`, precisely so *this* step never blocks), but CPython
    registers its own `concurrent.futures.thread._python_exit()` at import
    time — an atexit hook that unconditionally joins every worker thread ever
    created by any `ThreadPoolExecutor` in the process, ignoring `wait=`
    entirely. If one of those threads is still running (a task with no
    cooperative cancellation, stuck in a blocking call), the interpreter
    hangs *after* this function returns and after `main()`'s own frame has
    unwound — with no further log line, ever, since the hang is inside
    Python's own shutdown machinery, not this application's code. This is
    the exact mechanism `BUG-041` already root-caused for one specific task
    (`ScanCoordinator`'s auto-discover); `BUG-052` reproduced the same
    process-level symptom (`App stopped.` printed, process never returns)
    from a different, still-unidentified task — its own report's first
    suggested next step was "capture which thread is still alive", which had
    no log evidence to work from. This closes that gap generically, for
    every future occurrence, not just the one already diagnosed.

    The main thread itself is always alive at this point (this function
    runs on it) and is deliberately excluded — it is not what keeps the
    process from exiting.
    """
    survivors = [
        thread
        for thread in threading.enumerate()
        if thread is not threading.main_thread()
        and not thread.daemon
        and thread.is_alive()
    ]
    if not survivors:
        return

    names = ", ".join(f"{thread.name!r}" for thread in survivors)
    message = (
        f"{len(survivors)} non-daemon thread(s) still alive after engine "
        f"shutdown — the process will hang at exit until they finish "
        f"(BUG-052 class): {names}\n"
        + "\n".join(_format_thread_stack(thread) for thread in survivors)
    )
    if hasattr(app_engine, "context") and hasattr(app_engine.context, "logger"):
        app_engine.context.logger.warning(message)
    else:
        print(message)


def _install_exception_handler(app_engine) -> None:
    """Install a global Qt exception handler that logs and shows a resizable dialog.

    `BUG-048`: showing the dialog used to be unconditional. `QDialog.exec()`
    is modal and blocking — under a headless Qt platform (this project's own
    test/CI runs, `QT_QPA_PLATFORM=offscreen`) there is no window manager and
    no user, so nothing can ever dismiss it. Any uncaught exception reaching
    this handler — anywhere, any time after `build()` installs it — hung the
    real process forever instead of letting it exit non-zero, confirmed by
    fault injection in `tests/sanity/test_self_check_process.py` even after
    `teardown()` had already finished its own cleanup. A hang here is strictly
    worse than a crash: it gives no signal that anything is wrong.
    """

    def _handler(exc_type, exc_value, exc_tb) -> None:
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))

        if hasattr(app_engine, "context") and hasattr(app_engine.context, "logger"):
            app_engine.context.logger.error(
                f"Uncaught UI Exception: {exc_value}\n{tb_str}"
            )
        else:
            print(f"Uncaught UI Exception:\n{tb_str}")

        if is_headless_qt_platform():
            # No human is there to see or dismiss a dialog — the log line
            # above is the only report this session gets, and that is
            # correct: reporting loudly beats hanging silently.
            return

        dialog = CriticalErrorDialog(
            title="Critical System Error",
            message="An unexpected error occurred in the UI layer.",
            error_details=str(exc_value),
            traceback_str=tb_str,
        )
        dialog.exec()

    sys.excepthook = _handler


def _apply_font(app: QApplication, config: IConfig) -> None:
    """Apply the preferred monospace font read from config, with a safe fallback chain."""
    family = config.get(ConfigKeys.UI_FONT_FAMILY, "Consolas")
    size = config.get(ConfigKeys.UI_FONT_SIZE, 10, cast=int)
    fallbacks = config.get(ConfigKeys.UI_FONT_FALLBACKS, ["Consolas"])

    font = QFont(family, size)
    font.setStyleHint(QFont.Monospace)
    font.insertSubstitutions(family, fallbacks)
    app.setFont(font)


def _apply_theme(app: QApplication, config: IConfig) -> None:
    """Apply qdarktheme, replacing the default accent color with the one from config.

    @details The fallback below reads `Palette.ACCENT` rather than repeating the hex
    literal — EPIC-005B found this was the only place the app still hardcoded its own
    copy of the accent color outside `Palette`, once `qss/style.qss` (dead, unloaded
    since the BOT-030 QML migration) was confirmed orphaned and removed.
    """
    accent = config.get(ConfigKeys.UI_THEME_ACCENT_COLOR, Palette.ACCENT)
    replace = config.get(
        ConfigKeys.UI_THEME_REPLACE_COLOR,
        "rgba(138.000, 180.000, 247.000, 1.000)",
    )

    raw = qdarktheme.load_stylesheet("dark")
    app.setStyleSheet(raw.replace(replace, accent))


if __name__ == "__main__":
    main()
