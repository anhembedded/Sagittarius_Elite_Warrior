"""Guard: the shared composition path names no UI package (`EPIC-038A`).

**Why this exists.** `create_app` is what the headless entry point (and the
`run` host after it) builds. A machine that runs the bots with no display has no
PySide6, and until `EPIC-038A` the process could not even import the composition
root there: `system_error_report.py` imported the Engine's Qt package for an
event only the GUI can publish. Nothing noticed, because every test runs with
Qt installed.

**What it enforces.** Starting from `src/shell/composition_root.py` and
`src/main.py`, it follows every module-level import that resolves to a file in
this checkout, plus each package's `__init__.py` on the way (importing `a.b.c`
runs `a/__init__` and `a/b/__init__`), resolving a relative import (`from .handler import X`) against the importing file's package so the handlers that use them are walked too, and fails on a module-level import of
`PySide6`, `shiboken6`, `pyqtgraph` or `sagittarius_engine.extensions.pyside_mvc`.
Imports under `if TYPE_CHECKING:` and inside a function body are not module-level
imports; the three `core/contracts` files that name `QWidget` that way are the
only ones today.

**Imports by path (`PRO-014`).** The bounded contexts' classes, the headless commands and the
writable boot are named by `Deferred("package.module:attribute")` or `ModuleEntry(id, ...)`
instead of imported, and a run that uses them imports them, so the walk follows those
module-level strings as it follows an import. It stops at a `ui` package: a contribution's
widgets are deferred precisely so a headless run never imports them (the desktop entry
`app_bootstrapper` is under `presentation/ui`).

It is the static half. The dynamic half is
`tests/sanity/test_the_app_boots_without_pyside6.py`, which boots with the
packages blocked and also catches what is imported at run time (the Engine's
own modules, a lookup by `importlib.import_module`). This half names the file
and line, and runs in the unit tier on every commit.

Mutation check: add `import PySide6` to `composition_root.py` (or to any module
it imports) and this guard fails naming that line.

Stdlib only: no Qt, no Engine.

Retire when: the application has no Qt front end, or every entry point may
assume PySide6 is installed.
"""

from __future__ import annotations

import ast
from collections import deque
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
#: The checkout's directory name, which every first-party absolute import starts with.
_PACKAGE = _REPO_ROOT.name

#: The entry points whose module-level imports must stay Qt-free.
_ROOTS = ("src/shell/composition_root.py", "src/main.py")

_BANNED = (
    "PySide6",
    "shiboken6",
    "pyqtgraph",
    "sagittarius_engine.extensions.pyside_mvc",
)

#: The closure is large (the whole shell, the modules' module classes
#: reached by path, the infrastructure adapters). A walk that finds fewer modules than this lost its
#: subject, which would pass vacuously.
_MIN_MODULES = 150


@dataclass(frozen=True)
class _Import:
    module: str  # empty for `from . import x`
    names: tuple[str, ...]
    line: int
    level: int = 0  # leading dots of a relative import


def _is_type_checking(test: ast.expr) -> bool:
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def _module_level_imports(statements: list[ast.stmt]) -> list[_Import]:
    """Imports that run when the module is imported: not in a function body, not
    under `if TYPE_CHECKING:`."""
    found: list[_Import] = []
    for node in statements:
        if isinstance(node, ast.Import):
            found.extend(_Import(a.name, (), node.lineno) for a in node.names)
        elif isinstance(node, ast.ImportFrom) and (node.level > 0 or node.module):
            found.append(
                _Import(
                    node.module or "",
                    tuple(a.name for a in node.names),
                    node.lineno,
                    node.level,
                )
            )
        elif isinstance(node, ast.If):
            if not _is_type_checking(node.test):
                found.extend(_module_level_imports(node.body))
            found.extend(_module_level_imports(node.orelse))
        elif isinstance(node, ast.Try):
            for block in (node.body, node.orelse, node.finalbody):
                found.extend(_module_level_imports(block))
            for handler in node.handlers:
                found.extend(_module_level_imports(handler.body))
        elif isinstance(node, ast.With | ast.ClassDef):
            found.extend(_module_level_imports(node.body))
    return found


def _by_path_modules(statements: list[ast.stmt]) -> list[str]:
    """The first-party modules a module-level `Deferred("pkg.mod:attr")` or
    `ModuleEntry("id", "Class")` names, other than a `ui` package's."""
    found: list[str] = []
    for statement in statements:
        if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for node in ast.walk(statement):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            first = node.args[0] if node.args else None
            if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
                continue
            if node.func.id == "Deferred" and ":" in first.value:
                module = first.value.partition(":")[0]
            elif node.func.id == "ModuleEntry":
                module = f"{_PACKAGE}.src.modules.{first.value}.module"
            else:
                continue
            if "ui" not in module.split("."):
                found.append(module)
    return found


def _is_banned(module: str) -> bool:
    return any(module == b or module.startswith(b + ".") for b in _BANNED)


def _absolute(imported: _Import, importing_file: Path, root: Path) -> str:
    """The dotted name `imported` names, resolving leading dots against the
    package of `importing_file` (its directory, for a module and an `__init__`
    alike)."""
    if imported.level == 0:
        return imported.module
    package = [_PACKAGE, *importing_file.parent.relative_to(root).parts]
    base = package[: len(package) - (imported.level - 1)]
    return ".".join([*base, imported.module] if imported.module else base)


def _file_of(dotted: str, root: Path) -> Path | None:
    """The file a first-party dotted module name resolves to, else None."""
    prefix = _PACKAGE + "."
    if not dotted.startswith(prefix):
        return None
    relative = Path(*dotted[len(prefix) :].split("."))
    as_module = root / relative.with_suffix(".py")
    if as_module.is_file():
        return as_module
    as_package = root / relative / "__init__.py"
    return as_package if as_package.is_file() else None


def _with_parent_packages(dotted: str, root: Path) -> list[Path]:
    """The files importing `dotted` executes: each ancestor package's
    `__init__.py`, then the module itself."""
    parts = dotted.split(".")
    files: list[Path] = []
    for end in range(2, len(parts) + 1):
        target = _file_of(".".join(parts[:end]), root)
        if target is not None:
            files.append(target)
    return files


def _reachable_files() -> tuple[set[Path], list[str]]:
    """Every file the roots import at module level, and the banned imports met."""
    return _walk([_REPO_ROOT / root for root in _ROOTS], _REPO_ROOT)


def _walk(roots: list[Path], repo: Path) -> tuple[set[Path], list[str]]:
    seen: set[Path] = set()
    violations: list[str] = []
    queue: deque[Path] = deque(roots)
    while queue:
        path = queue.popleft()
        if path in seen:
            continue
        seen.add(path)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for imported in _module_level_imports(tree.body):
            where = f"{path.relative_to(repo).as_posix()}:{imported.line}"
            absolute = _absolute(imported, path, repo)
            if _is_banned(absolute):
                violations.append(f"{where} imports {absolute}")
                continue
            candidates = [absolute] + [f"{absolute}.{name}" for name in imported.names]
            for candidate in candidates:
                queue.extend(_with_parent_packages(candidate, repo))
        for module in _by_path_modules(tree.body):
            queue.extend(_with_parent_packages(module, repo))
    return seen, violations


def test_a_relative_import_is_followed() -> None:
    """The handlers under `modules/*/application/**` reach each other only
    through `from .handler import ...`; a walk that skips them scans a seventh
    of the path less than it claims. Probe: this file reaches one of them."""
    reached, _ = _reachable_files()
    handlers = [p for p in reached if p.name == "handler.py"]
    assert handlers, "no `handler.py` reached: relative imports are not followed"


def test_a_relative_import_of_a_qt_importing_module_is_a_violation(
    tmp_path: Path,
) -> None:
    """Mutation, kept as a test, on a throwaway tree named like the checkout: a
    relative import resolves to the module it names, and that module's own
    banned import is then reported with its file and line."""
    package = tmp_path / _PACKAGE / "src" / "shell"
    package.mkdir(parents=True)
    importer = package / "importer.py"
    importer.write_text("from .qt_module import X\n", encoding="utf-8")
    (package / "qt_module.py").write_text("import PySide6\nX = 1\n", encoding="utf-8")

    _, found = _walk([importer], tmp_path / _PACKAGE)

    assert found == ["src/shell/qt_module.py:1 imports PySide6"], found


def test_the_walk_has_a_subject() -> None:
    reached, _ = _reachable_files()
    assert len(reached) >= _MIN_MODULES, (
        f"only {len(reached)} modules reached from {_ROOTS}; the walk lost its "
        "subject (a moved root, or the resolver stopped following imports)"
    )
    assert _REPO_ROOT / "src/shell/system_failure_log.py" in reached


def test_the_shared_composition_path_imports_no_ui_package() -> None:
    _, violations = _reachable_files()
    assert violations == [], (
        "the composition shared by the headless entry point imports a UI package "
        "at module level, so it cannot boot where PySide6 is not installed. Move "
        "the import behind the GUI wiring (src/shell/gui_wiring.py) or "
        "under `if TYPE_CHECKING:`:\n" + "\n".join(f"  - {v}" for v in violations)
    )


def test_a_module_named_by_path_is_followed_and_a_ui_one_is_not(tmp_path: Path) -> None:
    """Mutation, kept as a test (`PRO-014`): a `Deferred` target that imports Qt is reported at
    its own import, and one under a `ui` package is left alone, as a contribution's widgets are."""
    package = tmp_path / _PACKAGE / "src" / "shell"
    package.mkdir(parents=True)
    root = package / "root.py"
    root.write_text(
        "from x import Deferred\n"
        f'_A = Deferred("{_PACKAGE}.src.shell.qt_module:X")\n'
        f'_B = Deferred("{_PACKAGE}.src.shell.ui.widget:Y")\n',
        encoding="utf-8",
    )
    (package / "qt_module.py").write_text("import PySide6\n", encoding="utf-8")
    (package / "ui").mkdir()
    (package / "ui" / "widget.py").write_text("import PySide6\n", encoding="utf-8")

    _, found = _walk([root], tmp_path / _PACKAGE)

    assert found == ["src/shell/qt_module.py:1 imports PySide6"], found
