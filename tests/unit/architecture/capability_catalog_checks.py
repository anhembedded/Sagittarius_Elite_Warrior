"""Pure checks behind the capability-catalog guard (`EPIC-037A`): what a module defines,
what a file imports, which support unit owns a file. No test lives here, so the guard and
its probes stay under the 400-line ceiling they enforce on others
(`test_god_files_only_shrink.py`).

Stdlib only: no Qt, no Engine.
"""

from __future__ import annotations

import ast
from pathlib import Path

from Sagittarius_Elite_Warrior.scripts.render_capability_index import Capability

#: The checkout's directory name, which every absolute import in `src/` starts with.
PACKAGE = Path(__file__).resolve().parents[3].name

#: Directories that roll up into their parent unit instead of being one.
ROLLS_UP = frozenset({"contracts", "adapters", "assets", "__pycache__"})
UNIT_DEPTH = 2


def defined_names(source: str) -> set[str]:
    """The names a module binds at its top level: classes, functions, assignments,
    type aliases and imports (an `__init__.py` re-exports by importing)."""
    names: set[str] = set()
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.TypeAlias) and isinstance(node.name, ast.Name):
            names.add(node.name.id)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.ImportFrom | ast.Import):
            names.update((a.asname or a.name).split(".")[0] for a in node.names)
    return names


def imports_from(source: str) -> set[tuple[str, str]]:
    """`(module, name)` for every absolute `from module import name` in `source`. A word in
    a string or comment is not an import, and a relative import names no module here."""
    return {
        (node.module, alias.name)
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module
        for alias in node.names
    }


def dotted_module(source_path: str) -> str:
    """The dotted module a repo-relative `.py` path is imported as (a package for
    `__init__.py`), under the checkout's own package name."""
    parts = Path(source_path).with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join((PACKAGE, *parts))


def imports_the_capability(user_source: str, capability: Capability) -> bool:
    """Whether `user_source` imports one of the capability's symbols **from the module that
    declares it, a package above it that re-exports it, or (for a package marker) a module
    inside the package**. A same-named symbol from an
    unrelated module is not a user."""
    declaring = dotted_module(capability.source)
    return any(
        name in capability.symbols
        and (
            declaring == module
            or declaring.startswith(module + ".")
            or module.startswith(declaring + ".")
        )
        for module, name in imports_from(user_source)
    )


def symbol_sites(root: Path, capability: Capability) -> list[Path]:
    """The files whose top-level names may satisfy `Use:`: the marked module itself, or for
    a package marker every module directly in the package."""
    marked = root / capability.source
    if marked.name != "__init__.py":
        return [marked]
    return sorted(marked.parent.glob("*.py"))


def unit_directories(support: Path) -> list[Path]:
    """Every directory at depth 1 or 2 under `support` that is a unit."""
    units: list[Path] = []
    frontier = [support]
    for _ in range(UNIT_DEPTH):
        frontier = [
            child
            for parent in frontier
            for child in sorted(parent.iterdir())
            if child.is_dir() and child.name not in ROLLS_UP
        ]
        units.extend(frontier)
    return units


def owning_unit(file: Path, units: set[Path]) -> Path | None:
    """The nearest ancestor directory of `file` that is a unit."""
    return next((p for p in file.parents if p in units), None)
