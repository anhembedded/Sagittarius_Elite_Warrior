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
import traceback
from dataclasses import dataclass

import qdarktheme
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.main import create_app
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette
from Sagittarius_Elite_Warrior.src.presentation.ui.common.process_exit import (
    exit_process,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.qt_platform import (
    is_headless_qt_platform,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components import (
    CriticalErrorDialog,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import MainWindow
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
    window = MainWindow(app_engine)
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
    # BUG-054: not `sys.exit()`. Shutdown finishing is not the same thing as
    # the process being able to die — see `process_exit`'s module docstring.
    exit_process(exit_code)


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
