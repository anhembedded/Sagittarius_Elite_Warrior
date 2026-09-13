"""What a module declares must match what it is (HLD §6.1, SDD-01b).

Four claims, each checkable, each a real failure mode:

1. **The module list and the disk agree, both ways.** A package under
   `src/modules/` that `shell/modules.py` does not list is dead code that looks
   alive; a listed module that is not on disk is a crash on the next boot.
2. **`dependencies` equals the contracts actually imported.** A surplus
   entry makes a module look coupled to something it never touches, which is how
   a migration order gets planned wrong; a shortfall hides a real coupling from
   the same plan. Both fail.
3. **A module declares an id.** `module_id` is what appears in every descriptor
   and every log line; the base class refuses an empty one.
4. **`contribute()` imports no widget module.** Checked by a `sys.modules`
   snapshot in `test_module_contribution_laziness`; this file covers the static
   half — the declarations.

Phase 0 PR 0.2 ships the mechanism with an empty `MODULES`, so most of these
run against an empty set on purpose: they are live *before* the first module
lands, which is the only way the first module gets checked at all. The
`dependencies` check reads imports with `ast`, never a regex (`BOT-133`).
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.bounded_context_module import (
    BoundedContextModule,
)
from Sagittarius_Elite_Warrior.src.shell.modules import MODULES
from Sagittarius_Elite_Warrior.tests.unit.architecture.boundaries.imports import (
    imported_modules,
)
from Sagittarius_Elite_Warrior.tests.unit.architecture.boundaries.zones import (
    is_contracts_package,
    zone_of,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_ROOT = _REPO_ROOT / "src"
_MODULES_ROOT = _SRC_ROOT / "modules"


def _packages_on_disk() -> set[str]:
    if not _MODULES_ROOT.is_dir():
        return set()
    return {
        path.name
        for path in _MODULES_ROOT.iterdir()
        if path.is_dir() and not path.name.startswith(("_", "."))
    }


def _declared_ids() -> list[str]:
    return [module_cls.module_id for module_cls in MODULES]


def _module_python_files(module_id: str) -> list[Path]:
    return sorted(
        path
        for path in (_MODULES_ROOT / module_id).rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _contracts_imported_by(module_id: str) -> set[str]:
    """The `module_id`s whose `contracts/` this module's code imports."""
    found: set[str] = set()
    for path in _module_python_files(module_id):
        relative = path.relative_to(_SRC_ROOT).with_suffix("")
        parts = list(relative.parts)
        is_package = parts[-1] == "__init__"
        if is_package:
            parts = parts[:-1]
        importing = ".".join(parts)
        source = path.read_text(encoding="utf-8")
        for imported in imported_modules(importing, source, is_package=is_package):
            zone = zone_of(imported)
            if zone is None or not zone.startswith("modules/"):
                continue
            other = zone.split("/", 1)[1]
            if other != module_id and is_contracts_package(imported):
                found.add(other)
    return found


def test_the_module_root_matches_the_module_list() -> None:
    """Phase 0 PR 0.2: both sides are empty, and they are still compared —
    the first module to land is checked by a test that was already running."""
    assert _packages_on_disk() == set(_declared_ids())


def test_every_declared_module_is_a_bounded_context_module() -> None:
    for module_cls in MODULES:
        assert issubclass(module_cls, BoundedContextModule), module_cls


def test_no_module_id_is_declared_twice() -> None:
    declared = _declared_ids()
    assert len(declared) == len(set(declared)), f"duplicate module ids: {declared}"


def test_every_module_id_is_its_package_name() -> None:
    """The id is not a label: it is the package on disk, the `contributor_id` in
    every descriptor, and the name the Engine registers."""
    for module_cls in MODULES:
        assert (_MODULES_ROOT / module_cls.module_id).is_dir(), module_cls.module_id


def test_declared_dependencies_are_exactly_the_contracts_imported() -> None:
    for module_cls in MODULES:
        declared = set(module_cls.dependencies)
        imported = _contracts_imported_by(module_cls.module_id)
        surplus = sorted(declared - imported)
        shortfall = sorted(imported - declared)
        assert not surplus, (
            f"{module_cls.module_id}: declares a dependency on {surplus} but imports "
            f"nothing from their contracts/ — remove it, or the migration plan is "
            f"reading a coupling that does not exist."
        )
        assert not shortfall, (
            f"{module_cls.module_id}: imports contracts from {shortfall} without "
            f"declaring it — add it to `dependencies`, so the coupling is visible "
            f"where the module list is read."
        )


def test_no_module_declares_itself_as_a_dependency() -> None:
    for module_cls in MODULES:
        assert module_cls.module_id not in module_cls.dependencies


def test_every_declared_dependency_is_a_module_that_exists() -> None:
    known = set(_declared_ids())
    for module_cls in MODULES:
        unknown = sorted(set(module_cls.dependencies) - known)
        assert not unknown, (
            f"{module_cls.module_id} depends on unknown modules {unknown}"
        )


def test_the_contracts_reader_finds_a_cross_module_import() -> None:
    """The guard above passes trivially while `MODULES` is empty, so prove the
    reader it depends on actually sees a contracts import."""
    source = (
        "from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_klines "
        "import IHistoricalKlines\n"
    )
    found = imported_modules("modules.trading.application.x", source)
    assert found == {"modules.market_data.contracts.i_klines"}
    assert is_contracts_package(next(iter(found)))
