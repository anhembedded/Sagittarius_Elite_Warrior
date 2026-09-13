"""A bounded context's inside knows nothing about a UI toolkit (HLD §6.1).

The rule: no runtime import of `PySide6` or the Engine's `pyside_mvc` extension
under `modules/*/domain`, `modules/*/application`, `core/**` or
`support/indicators/**`. Imports inside `if TYPE_CHECKING:` are ignored — that
is precisely how `core/contracts` names `QWidget` in a factory signature while
importing no toolkit at runtime, and how a port can be typed against
`QtEventBridge` without depending on Qt.

Why it matters beyond tidiness: the day one of these packages imports Qt, its
tests need a `QApplication`, its code can be called only from the main thread,
and the rule that a port implementation "never touches Qt" (SDD, threading
contract) stops being checkable. `EPIC-008`'s Shared Kernel guard exists for the
same reason one layer down, and the two together are what keep the inside of the
application testable without a display.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_ROOT = _REPO_ROOT / "src"

#: Toolkit roots no Qt-free package may import at runtime.
_TOOLKIT_ROOTS = ("PySide6", "PyQt5", "PyQt6", "pyqtgraph")
#: The Engine's Qt extension — importing it is importing Qt transitively.
_ENGINE_QT_MODULE = "sagittarius_engine.extensions.pyside_mvc"

#: Globs, relative to `src/`, of the packages that must stay Qt-free. The
#: module ones match nothing until PR 0.4 creates `modules/`; the guard's
#: non-emptiness is covered by `core/`, which exists now, and by
#: `test_scanned_roots_are_not_empty.py`.
_QT_FREE_GLOBS = (
    "core/**/*.py",
    "modules/*/domain/**/*.py",
    "modules/*/application/**/*.py",
    "modules/*/contracts/**/*.py",
    "support/indicators/**/*.py",
)


def _is_type_checking_guard(node: ast.AST) -> bool:
    if not isinstance(node, ast.If):
        return False
    test = node.test
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"


def _runtime_nodes(tree: ast.AST):
    stack: list[ast.AST] = [tree]
    while stack:
        node = stack.pop()
        yield node
        if _is_type_checking_guard(node):
            stack.extend(node.orelse)
        else:
            stack.extend(ast.iter_child_nodes(node))


def _runtime_toolkit_imports(source: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for node in _runtime_nodes(ast.parse(source)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        else:
            continue
        for name in names:
            if name.split(".")[0] in _TOOLKIT_ROOTS or name.startswith(
                _ENGINE_QT_MODULE
            ):
                found.append((node.lineno, name))
    return found


def _qt_free_files() -> list[Path]:
    return sorted(
        {
            path
            for glob in _QT_FREE_GLOBS
            for path in _SRC_ROOT.glob(glob)
            if "__pycache__" not in path.parts
        }
    )


def test_there_are_qt_free_packages_to_check() -> None:
    """`core/` exists from Phase 0 on, so an empty scan means the globs or the
    tree moved — the vacuous-guard failure HLD §9.3 rule 4 forbids."""
    files = _qt_free_files()
    assert files, f"no Qt-free package found under {_SRC_ROOT}"
    assert any("core" in path.parts for path in files)


def test_no_qt_free_package_imports_a_toolkit_at_runtime() -> None:
    offenders = [
        f"  {path.relative_to(_REPO_ROOT).as_posix()}:{line}  {name}"
        for path in _qt_free_files()
        for line, name in _runtime_toolkit_imports(path.read_text(encoding="utf-8"))
    ]
    assert offenders == [], (
        "a Qt-free package imports a UI toolkit at runtime. Put the import in an\n"
        "`if TYPE_CHECKING:` block if it is only a type, or move the code that\n"
        "needs the toolkit into the module's `ui/` package.\n" + "\n".join(offenders)
    )


def test_type_checking_imports_are_allowed() -> None:
    source = (
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from PySide6.QtWidgets import QWidget\n"
    )
    assert _runtime_toolkit_imports(source) == []


def test_the_guard_sees_a_runtime_import() -> None:
    source = (
        "from PySide6.QtWidgets import QWidget\n"
        "import pyqtgraph\n"
        "from sagittarius_engine.extensions.pyside_mvc import BaseView\n"
    )
    assert sorted(name for _line, name in _runtime_toolkit_imports(source)) == [
        "PySide6.QtWidgets",
        "pyqtgraph",
        "sagittarius_engine.extensions.pyside_mvc",
    ]
