"""Every `import <Module>` in this app's QML must resolve against a QML module
the installed engine actually ships.

Why this exists (BUG-035, 2026-08-23): engine 2.0.0 renamed its QML module
`QmlShared` -> `Sagittarius.UI` and dropped the old name. All 26 of this app's
`.qml` files still imported `QmlShared 1.0`. The result was 69 red tests whose
visible errors were ~400 lines of
`TypeError: Cannot read property 'textPrimary' of null` — the Theme context
property appearing null because no component had loaded at all. The single real
cause, `module "QmlShared" is not installed`, appeared once, buried in Qt
messages inside the first failing test.

That is a bad failure signature for a one-line cause. This test turns the same
breakage into a single, immediate, named failure that says exactly which file
imports what and which modules are actually available — without needing Qt, a
QApplication, or a rendered scene.

Scope: engine-provided modules only. Qt's own modules (`QtQuick`,
`QtQuick.Controls`, ...) are resolved by Qt itself and are not our business
here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import sagittarius_engine.extensions.pyside_mvc as pyside_mvc_pkg

_SRC = Path(__file__).resolve().parents[4] / "src"
_PYSIDE_MVC_ROOT = Path(pyside_mvc_pkg.__file__).parent

#: `import Foo.Bar 1.0` / `import Foo 1.0` — captures the module name only.
_QML_IMPORT = re.compile(r"^\s*import\s+([A-Za-z][\w.]*)\s", re.MULTILINE)

#: Not engine-provided, so not checkable from a shipped qmldir — Qt's own
#: modules, resolved by Qt itself.
_NOT_ENGINE_PROVIDED = ("QtQuick", "QtQml", "Qt", "QtCharts", "QtGraphs")


def _engine_qml_modules() -> set[str]:
    """Module names declared by every `qmldir` the installed engine ships."""
    modules: set[str] = set()
    for qmldir in _PYSIDE_MVC_ROOT.rglob("qmldir"):
        for line in qmldir.read_text(encoding="utf-8").splitlines():
            if line.startswith("module "):
                modules.add(line.split(None, 1)[1].strip())
    return modules


def _app_qml_files() -> list[Path]:
    return sorted(_SRC.rglob("*.qml"))


def test_engine_actually_ships_at_least_one_qml_module() -> None:
    """Guard the guard: if the engine's qmldir discovery silently found
    nothing, every assertion below would pass vacuously."""
    modules = _engine_qml_modules()
    assert modules, (
        f"No qmldir found anywhere under {_PYSIDE_MVC_ROOT}. Either the engine "
        "stopped shipping its QML (check [tool.setuptools.package-data] in its "
        "pyproject.toml), or this test's discovery path is wrong. Until this "
        "passes, the import check below proves nothing."
    )


def test_app_qml_files_were_discovered() -> None:
    """Same reasoning: an empty file list would make the real test vacuous."""
    files = _app_qml_files()
    assert len(files) > 10, (
        f"Only {len(files)} .qml files found under {_SRC} — expected the app's "
        "full QML tree. Check this test's _SRC path resolution."
    )


def test_every_qml_import_resolves_to_a_shipped_engine_module() -> None:
    available = _engine_qml_modules()
    unresolved: list[str] = []

    for qml_file in _app_qml_files():
        text = qml_file.read_text(encoding="utf-8")
        for module in _QML_IMPORT.findall(text):
            if module.startswith(_NOT_ENGINE_PROVIDED):
                continue
            if module not in available:
                rel = qml_file.relative_to(_SRC)
                unresolved.append(f"  src/{rel}: import {module}")

    if unresolved:
        pytest.fail(
            "QML files import a module the installed engine does not ship:\n"
            + "\n".join(sorted(unresolved))
            + f"\n\nModules the engine actually ships: {sorted(available)}"
            + "\n\nThis is what BUG-035 looked like before it reached Qt: an "
            "engine upgrade renamed the module and every import silently "
            "stopped resolving. Fix the import lines, or pin/upgrade the engine."
        )
