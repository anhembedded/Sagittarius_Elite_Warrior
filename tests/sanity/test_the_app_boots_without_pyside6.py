"""`EPIC-038A` — the app boots with PySide6 absent, and CI keeps it so.

The shared composition (`create_app`) is what the headless entry point
(`main.py`) and, later, the `run` host build. It must not need Qt: a server has
no display and should not install Qt's system libraries (`libEGL`, `libGL`, …).
Nothing noticed Qt creeping back, because every other test runs with PySide6
installed — the fault this guard closes.

Every case runs in a **subprocess**. Blocking an import is process-wide and
permanent, so doing it inside pytest's process would also break every later
test; and a boot that finds `QApplication` already imported by the test session
proves nothing about the VPS.

Three facts are checked, because each one alone could pass vacuously:

1. the harness is honest: `find_spec` reports the blocked packages absent and
   importing one raises (a block that did nothing would let case 2 pass);
2. the full cycle — `create_app`, `boot`, `stop` — completes with the block, on
   an empty data root and no credentials, and `BotsModule.boot` says so;
3. the same cycle with PySide6 importable but no `QApplication` ever created
   (a developer's machine running a command), and neither case imports a UI
   package at all (`sys.modules` is read after `stop`).

Retire when: the application no longer has a Qt front end, or every entry point
may assume PySide6 is installed.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV

_REPO_ROOT = Path(__file__).resolve().parents[2]

#: A hang is a failure, not a long wait (`test_self_check_process.py`).
_PROCESS_BUDGET_SECONDS = 60

#: The four log lines `BotsModule.boot` writes (`modules/bots/module.py`): the
#: proof the bots module booted, not merely that nothing raised.
_BOTS_BOOT_LINES = (
    "Bots restored after start-up",
    "Bots subscribed to fills, ends, rejections, funding, ticks and the switch",
    "Bots watch the user-data stream's health",
    "Bots watch for the machine's sleep",
)

#: Every top-level name the headless path must not need.
_UI_PACKAGES = ("PySide6", "shiboken6", "pyqtgraph")

#: Imported by name from the Engine's Qt runtime; naming it from the shared
#: path is how `BUG`-class regressions of this guard would arrive.
_ENGINE_UI_PACKAGE = "sagittarius_engine.extensions.pyside_mvc"

_BLOCK_PRELUDE = f"""
import sys
for _name in {_UI_PACKAGES!r}:
    sys.modules[_name] = None
"""

_BOOT_CYCLE = f"""
import sys
from Sagittarius_Elite_Warrior.src.shell.app_config import load_app_config
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app

config_manager, _ = load_app_config(["headless"])
app = create_app(config_manager)
app.boot()
app.stop()

leaked = sorted(
    name for name in sys.modules
    if sys.modules[name] is not None
    and (name.split(".")[0] in {_UI_PACKAGES!r}
         or name.startswith({_ENGINE_UI_PACKAGE!r}))
)
assert not leaked, f"UI packages imported by the shared path: {{leaked[:10]}}"
print("BOOT_CYCLE_OK")
"""

_FIND_SPEC_HONEST = f"""
import importlib.util

for name in {_UI_PACKAGES!r}:
    assert importlib.util.find_spec(name) is None, f"{{name}} still found"
    try:
        __import__(name)
    except ImportError:
        continue
    raise AssertionError(f"{{name}} imported although blocked")
print("BLOCK_IS_HONEST")
"""

_QAPPLICATION_ABSENT = """
from PySide6.QtWidgets import QApplication
assert QApplication.instance() is None, "a QApplication exists in a headless run"
print("NO_QAPPLICATION")
"""


def _run(script: str, data_root: Path) -> subprocess.CompletedProcess[str]:
    """`script` in a fresh interpreter on its own, empty data root, with no
    credentials in the environment and no display."""
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("BINANCE_", "SEW_"))
    }
    env.update({DATA_ROOT_ENV: str(data_root), "QT_QPA_PLATFORM": "offscreen"})
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(_REPO_ROOT.parent),
        capture_output=True,
        text=True,
        timeout=_PROCESS_BUDGET_SECONDS,
        check=False,
        env=env,
    )


def _evidence(result: subprocess.CompletedProcess[str]) -> str:
    return (
        f"exit {result.returncode}\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )


def test_find_spec_reports_the_blocked_packages_absent(tmp_path: Path) -> None:
    result = _run(_BLOCK_PRELUDE + _FIND_SPEC_HONEST, tmp_path)

    assert result.returncode == 0, _evidence(result)
    assert "BLOCK_IS_HONEST" in result.stdout, _evidence(result)


def test_create_app_boots_and_stops_with_pyside6_blocked(tmp_path: Path) -> None:
    result = _run(_BLOCK_PRELUDE + _BOOT_CYCLE, tmp_path)

    assert result.returncode == 0, _evidence(result)
    assert "BOOT_CYCLE_OK" in result.stdout, _evidence(result)
    log = result.stdout + result.stderr
    for line in _BOTS_BOOT_LINES:
        assert line in log, f"{line!r} missing from the run log\n{_evidence(result)}"
    assert "App stopped." in log, _evidence(result)


def test_create_app_boots_and_stops_with_pyside6_importable_but_no_qapplication(
    tmp_path: Path,
) -> None:
    result = _run(_BOOT_CYCLE + _QAPPLICATION_ABSENT, tmp_path)

    assert result.returncode == 0, _evidence(result)
    assert "BOOT_CYCLE_OK" in result.stdout, _evidence(result)
    assert "NO_QAPPLICATION" in result.stdout, _evidence(result)
