"""The registry rows of the guards that keep a module's dependents honest.

Split from `scanned_roots_registry.py`, which sits at the 400-line ceiling; the
registry spreads `MODULE_DEPENDENCY_GUARDS` into `GUARDS`, so nothing that reads
the registry changes. Same shape, same rules: register the directories a guard
*scans*.
"""

from __future__ import annotations

MODULE_DEPENDENCY_GUARDS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "tests/unit/architecture/test_no_module_depends_on_operations.py",
        (("src", "*.py"),),
    ),
)
