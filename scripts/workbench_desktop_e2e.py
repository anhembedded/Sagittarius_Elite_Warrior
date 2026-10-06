"""Desktop E2E for the workbench: open, use, rearrange, restart (`EPIC-033I`, `EPIC-033K`).

Why this exists
---------------
`test_main_window_state.py` rearranges and restarts every mode, but offscreen:
no window manager, no real paint, no real mouse. `EPIC-033I` (Trade) and
`EPIC-033K` (Bots) close only with the same journey on a real display, which
no cloud session has. This script is that journey, one command on the user's
own machine.

What it does
------------
Two runs of the real application (`app_bootstrapper.build()`, the production
boot), each in its own process, both over one scratch `SEW_DATA_ROOT`, so the
user's own layout, logs and bot state are never touched:

1. **arrange**: show the window; for every mode, click its mode-bar button
   with a real mouse click, take a picture, rearrange the mode (every dock to
   the other side, every other bar hidden), take a picture; close the app
   through its real shutdown, which saves the layout.
2. **check**: start the app again; for every mode, click its button and
   compare each dock and toolbar with how it was left; take a picture.

It prints one line per problem, the folder holding the pictures, and exits 1
on any problem. Look at the pictures too: a layout can be restored and still
paint wrong.

Run only on a machine with a real display session, from the checkout:
    python scripts/workbench_desktop_e2e.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from types import TracebackType

# Run bare, nothing puts the checkout's parent on the path; the app and the
# layout checks are imported by their package names, as in `measure_process.py`.
sys.path.insert(
    0,
    str(
        next(
            p
            for p in Path(__file__).resolve().parents
            if (p / "pyproject.toml").is_file()
        ).parent
    ),
)

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QToolBar, QWidget

from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV
from Sagittarius_Elite_Warrior.src.presentation.ui.app_bootstrapper import (
    AppRuntime,
    build,
    teardown,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import MainWindow
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_layout_checks import (
    rearrange,
    restart_problems,
)

ARRANGE = "arrange"
CHECK = "check"
LAYOUTS_FILE = "layouts.json"
PROBLEMS_FILE = "problems.json"
PICTURES_DIR = "pictures"
MODE_BAR = "workbench::mode_bar"
#: Long enough for a mode's first paint and its deferred loads to settle on
#: a real display; the check compares layouts, not timing.
_SETTLE_MS = 800
_HEADLESS_PLATFORMS = frozenset({"offscreen", "minimal"})


def _click_mode(window: MainWindow, route: str) -> str | None:
    """Clicks a mode's mode-bar button with a real mouse click; answers a
    problem line, or None when the mode is now the current one."""
    bar = window.findChild(QToolBar, MODE_BAR)
    action = window.findChild(QAction, f"action::workbench.mode.{route}")
    button = bar.widgetForAction(action) if bar and action else None
    if not isinstance(button, QWidget):
        return f"{route}: no mode-bar button to click"
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    QTest.qWait(_SETTLE_MS)
    current = window.navigation.current
    return None if current == route else f"{route}: a click left {current} current"


def _picture(window: MainWindow, folder: Path, name: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    window.grab().save(str(folder / f"{name}.png"))


#: Every exception that reached the top of the event loop during this run.
_UNCAUGHT: list[str] = []


def _record_uncaught(
    kind: type[BaseException], error: BaseException, trace: TracebackType | None
) -> None:
    """Replaces the app's handler, whose modal dialog nobody here can close:
    an exception is a problem of this run, printed and counted."""
    text = "".join(traceback.format_exception(kind, error, trace))
    sys.stderr.write(text)
    _UNCAUGHT.append(f"uncaught {kind.__name__}: {error}")


def _open() -> tuple[AppRuntime, MainWindow]:
    runtime = build()
    sys.excepthook = _record_uncaught
    window = runtime.window
    window.show()
    QTest.qWaitForWindowExposed(window)
    QTest.qWait(_SETTLE_MS)
    return runtime, window


def _arrange(work: Path) -> list[str]:
    runtime, window = _open()
    problems: list[str] = []
    layouts: dict[str, dict[str, str]] = {}
    for number, route in enumerate(window.navigation.modes(), 1):
        problem = _click_mode(window, route)
        if problem:
            problems.append(problem)
            continue
        _picture(window, work / PICTURES_DIR, f"{number:02d}-{route}-1-opened")
        layouts[route] = rearrange(window.hosts[route])
        QTest.qWait(_SETTLE_MS)
        _picture(window, work / PICTURES_DIR, f"{number:02d}-{route}-2-rearranged")
    (work / LAYOUTS_FILE).write_text(json.dumps(layouts, indent=2), "utf-8")
    teardown(runtime)
    return problems


def _check(work: Path) -> list[str]:
    layouts = json.loads((work / LAYOUTS_FILE).read_text("utf-8"))
    runtime, window = _open()
    problems: list[str] = []
    for number, (route, layout) in enumerate(layouts.items(), 1):
        problem = _click_mode(window, route)
        if problem:
            problems.append(problem)
            continue
        problems += [
            f"{route}: {line}" for line in restart_problems(layout, window.hosts[route])
        ]
        _picture(window, work / PICTURES_DIR, f"{number:02d}-{route}-3-restarted")
    teardown(runtime)
    return problems


def _run_phase(phase: str, work: Path) -> int:
    problems = _arrange(work) if phase == ARRANGE else _check(work)
    problems += _UNCAUGHT
    (work / f"{phase}-{PROBLEMS_FILE}").write_text(json.dumps(problems), "utf-8")
    return 1 if problems else 0


def _drive() -> int:
    platform = os.environ.get("QT_QPA_PLATFORM", "")
    if platform in _HEADLESS_PLATFORMS:
        sys.stderr.write(
            f"needs a real display: unset QT_QPA_PLATFORM (it is {platform!r})\n"
        )
        return 2
    work = Path(tempfile.mkdtemp(prefix="sew-desktop-e2e-"))
    env = {**os.environ, DATA_ROOT_ENV: str(work / "data")}
    problems: list[str] = []
    for phase in (ARRANGE, CHECK):
        run = subprocess.run(  # noqa: S603 -- this interpreter, this file, fixed arguments
            [sys.executable, __file__, phase, str(work)], env=env, check=False
        )
        found = work / f"{phase}-{PROBLEMS_FILE}"
        if found.is_file():
            problems += json.loads(found.read_text("utf-8"))
        elif run.returncode:
            problems.append(f"{phase}: the app exited with {run.returncode}")
        if phase == ARRANGE and not (work / LAYOUTS_FILE).is_file():
            break
    for line in problems:
        sys.stdout.write(f"PROBLEM: {line}\n")
    sys.stdout.write(f"PICTURES: {work / PICTURES_DIR}\n")
    sys.stdout.write(f"RESULT: {'FAIL' if problems else 'PASS'}\n")
    return 1 if problems else 0


def main(argv: list[str]) -> int:
    match argv:
        case [phase, work] if phase in (ARRANGE, CHECK):
            return _run_phase(phase, Path(work))
    return _drive()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
