"""Walking `src/` and applying the policy to every file it contains."""

from __future__ import annotations

from pathlib import Path

from .allowlist import Violation
from .imports import imported_modules
from .rules import import_is_allowed

#: The composition root may import anything; it is the one place wiring happens.
COMPOSITION_ROOT_FILES = frozenset({"binance_bot_module.py", "main.py"})


def scanned_files(src_root: Path) -> list[Path]:
    return sorted(
        p
        for p in src_root.rglob("*.py")
        if not (p.parent == src_root and p.name in COMPOSITION_ROOT_FILES)
    )


def module_name(src_root: Path, py_file: Path) -> tuple[str, bool]:
    """Dotted name relative to `src/`, and whether the file is a package
    `__init__` (which changes how its relative imports resolve)."""
    parts = list(py_file.relative_to(src_root).with_suffix("").parts)
    is_package = parts[-1] == "__init__"
    if is_package:
        parts = parts[:-1]
    return ".".join(parts), is_package


def find_violations(src_root: Path) -> list[Violation]:
    violations: set[Violation] = set()
    for py_file in scanned_files(src_root):
        importing, is_package = module_name(src_root, py_file)
        source = py_file.read_text(encoding="utf-8")
        for imported in imported_modules(importing, source, is_package=is_package):
            if not import_is_allowed(importing, imported):
                violations.add(Violation(importing, imported))
    return sorted(violations)
