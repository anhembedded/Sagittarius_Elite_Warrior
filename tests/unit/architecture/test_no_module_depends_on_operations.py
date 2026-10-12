"""`operations` listens and is depended on by none (`EPIC-038` D4,
`DESIGN_2026-10-09_headless_operation.md` §3).

The module that runs the application unattended reads what the others
*contribute*; if `bots` or `trading` imported it, the host would be a
prerequisite of the domain and a headless-only change could break the GUI.
`test_module_declarations.py` only checks that a module's declared dependencies
equal its imports, so a module could declare `operations` and import it with
every other guard green. This is the missing half.

Only the composition (`src/shell`, which lists the module) and `operations`
itself may name it.

Retire when: decision D4 is overruled and `operations` is folded into another
context, or the dependency rule moves into the boundary guard's rule table.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.tests.unit.architecture.boundaries.imports import (
    imported_modules,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC = _REPO_ROOT / "src"
_OPERATIONS = "modules.operations"
_MAY_NAME_OPERATIONS = (_SRC / "modules" / "operations", _SRC / "shell")


def _dotted(path: Path) -> str:
    return ".".join(path.relative_to(_SRC).with_suffix("").parts)


def _is_exempt(path: Path) -> bool:
    return any(root in path.parents for root in _MAY_NAME_OPERATIONS)


def _importers_of_operations(root: Path = _SRC) -> list[str]:
    offenders: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts or _is_exempt(path):
            continue
        imported = imported_modules(
            _dotted(path),
            path.read_text(encoding="utf-8"),
            is_package=path.name == "__init__.py",
        )
        if any(
            name == _OPERATIONS or name.startswith(f"{_OPERATIONS}.")
            for name in imported
        ):
            offenders.append(path.relative_to(_REPO_ROOT).as_posix())
    return offenders


def test_no_module_depends_on_operations() -> None:
    assert _importers_of_operations() == []
