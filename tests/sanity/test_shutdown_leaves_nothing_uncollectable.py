"""The app's interpreter exits with nothing uncollectable (`BUG-152`).

PySide6 6.9–6.11 leaves one object `gc` cannot collect for every `QObject`
class that declares a `QtCore.Property` and is still alive at exit; Python
reports them as `gc: N uncollectable objects at shutdown`, a
`ResourceWarning` the gate's prescribed grep exists to catch. The sanity run
printed it on every run. The app's own Properties went in `EPIC-033M`; the
rest came from the Engine's QML layer, which `pyside_mvc` loaded eagerly
(fixed there, Engine `BUG-023`) and which three app view models still
inherited through `BaseQmlViewModel`.

Both checks run in a fresh interpreter: the suite around them has already
imported whatever other tests needed, and what is alive at exit is a
property of the process.

- The structural one is the mechanism: every module under `src/` imported,
  no loaded `QObject` class (the app's or the Engine's) declares a
  `QtCore.Property`, and the Engine's QML layer is not loaded. The warning
  itself depends on the order modules are torn down, so its absence alone
  is not proof.
- The direct one is the symptom: importing the three view models that
  carried a Property exits without the warning.

Retire when: PySide6 collects a Property class at exit, or the app leaves
PySide6.
"""

from __future__ import annotations

import importlib
import inspect
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Property, QObject

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPO_PARENT = _REPO_ROOT.parent

_THIS_MODULE = (
    "Sagittarius_Elite_Warrior.tests.sanity.test_shutdown_leaves_nothing_uncollectable"
)

#: The Engine's QML layer, which `pyside_mvc` loads only on first use since
#: Engine `BUG-023`; loading it brings its Property classes with it.
_QML_LAYER_SUFFIXES = (
    ".pyside_mvc.kit.card_model",
    ".pyside_mvc.runtime.base_view_model",
)


def what_leaks_at_exit() -> list[str]:
    """Every loaded `QObject` class that declares a `QtCore.Property`, by
    itself or through a base, and every loaded module of the Engine's QML
    layer: what will be uncollectable when this process exits."""
    found = {
        f"{value.__module__}.{value.__qualname__}"
        for module in list(sys.modules.values())
        for value in list(vars(module).values())
        if inspect.isclass(value)
        and issubclass(value, QObject)
        and any(
            isinstance(attribute, Property)
            for klass in value.__mro__
            for attribute in vars(klass).values()
        )
    }
    qml_layer = {name for name in sys.modules if name.endswith(_QML_LAYER_SUFFIXES)}
    return sorted(found | qml_layer)


def import_every_src_module() -> None:
    """`src/` is namespace packages, which `pkgutil.walk_packages` does not enter."""
    paths = sorted((_REPO_ROOT / "src").rglob("*.py"))
    if not paths:
        raise FileNotFoundError("no module under src/: the scan would prove nothing")
    for path in paths:
        if path.name == "__main__.py":
            continue
        parts = path.relative_to(_REPO_PARENT).with_suffix("").parts
        importlib.import_module(
            ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
        )


_LEAKS_AFTER_IMPORTING_SRC = (
    f"from {_THIS_MODULE} import import_every_src_module, what_leaks_at_exit\n"
    "import_every_src_module()\n"
    "print('\\n'.join(what_leaks_at_exit()))\n"
)

_THE_VIEW_MODELS = (
    "Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view_model",
    "Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_view_model",
    "Sagittarius_Elite_Warrior.src.support.ui_kit.status_view_model",
)


def _run(code: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "QT_QPA_PLATFORM": "offscreen",
        "PYTHONPATH": str(_REPO_PARENT),
    }
    return subprocess.run(
        [sys.executable, "-W", "default", "-c", code],
        capture_output=True,
        text=True,
        env=env,
        cwd=_REPO_PARENT,
        timeout=120,
        check=False,
    )


def test_no_src_module_loads_a_qobject_class_with_a_qt_property() -> None:
    result = _run(_LEAKS_AFTER_IMPORTING_SRC)

    assert result.returncode == 0, result.stderr
    offenders = result.stdout.split()
    assert offenders == [], (
        "these QObject classes declare a QtCore.Property, or the Engine's QML "
        f"layer was loaded, so each leaks an uncollectable object at exit: {offenders}"
    )


def test_importing_the_view_models_exits_without_uncollectable_objects() -> None:
    result = _run("; ".join(f"import {module}" for module in _THE_VIEW_MODELS))

    assert result.returncode == 0, result.stderr
    assert "uncollectable" not in result.stderr, result.stderr


def test_the_booted_app_loads_no_qobject_class_with_a_qt_property(booted_app) -> None:
    """Boot runs code an import does not: the engine-capability check once
    looked up `create_quick_widget`, and the lookup alone loaded the Engine's
    QML layer. The sanity tier runs alone, so what this process holds after
    the real boot is what the app loads."""
    leaks = what_leaks_at_exit()

    assert leaks == [], (
        f"after the real boot these will be uncollectable at exit: {leaks}"
    )
