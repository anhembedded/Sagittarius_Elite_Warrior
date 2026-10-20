"""`BUG-237` - the composition root hands PySide6 a pydantic that is whole, not half-loaded.

**Why.** `pydantic` 2.13 loads most of itself lazily: `from pydantic import BaseModel`
(what the engine's `PydanticValidationMiddleware` writes, and `composition_root` imports
it) leaves `pydantic.fields` and `pydantic._internal._validators` unloaded until the first
model class is defined. PySide6 installs an import hook (`shibokensupport.feature`) that,
on the first import of a module it has not seen, calls `inspect.getsource` on it, and that
reads `module.__wrapped__`. For `pydantic.errors` that runs a module `__getattr__` which
imports `pydantic._internal._validators` - while that very module is the one being
imported. So the order *engine middleware, then PySide6, then the first model class* dies
with `cannot import name 'import_string' from partially initialized module`. `src/main.py`
imports `composition_root` before the GUI imports PySide6, and the bots integration
`conftest.py` imports it before pytest-qt does, so both orders are real.

This runs the order in a fresh interpreter: a test process has PySide6 loaded already
(pytest-qt), so only a child shows what the first import of each does.

Retire when: `pydantic` stops loading lazily, or PySide6's import hook stops reading
`__wrapped__` of modules it did not load.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

#: The parent of the repository: `from Sagittarius_Elite_Warrior.src...` resolves there.
_WORKSPACE = Path(__file__).resolve().parents[4]

_ORDER = """
import Sagittarius_Elite_Warrior.src.shell.composition_root
import PySide6.QtCore
from Sagittarius_Elite_Warrior.src.modules.backtesting.application.run_static_backtest import command
from Sagittarius_Elite_Warrior.src.modules.market_data.cli import sync_cmd
print("whole")
"""


def test_a_model_class_defines_after_the_composition_root_then_pyside6_loaded() -> None:
    result = subprocess.run(
        [sys.executable, "-c", _ORDER],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join(
                [str(_WORKSPACE), os.environ.get("PYTHONPATH", "")]
            ),
            "QT_QPA_PLATFORM": "offscreen",
        },
    )
    assert result.returncode == 0, result.stderr[-1500:]
    assert result.stdout.strip() == "whole"
