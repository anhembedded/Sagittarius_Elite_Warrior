"""The bots module's shared service shell stays grouped by feature and kind-neutral (`BOT-177`).

`bots/application/services/` once held 111 flat modules, and a reader could not tell
which of them every bot kind shares from which only the Grid knows. `BOT-177` split it:
the shell stays in `services/`, grouped into feature sub-packages, and everything that
knows the Grid lives in `application/kinds/grid/`. Two guards keep that split:

1. **Nothing sits loose at the top of `services/`.** A new service goes into a feature
   sub-package; the flat list cannot grow back.
2. **The shell does not import a kind.** Nothing under `services/` imports
   `application/kinds/` or `domain/grid/`. The files that do today are listed in
   `baseline_bots_shell_imports_a_kind.txt`. That list only shrinks: a file not on it
   fails, and a file on it that no longer imports a kind must be deleted from it in the
   same commit. It is the work list of `EPIC-040B` and `EPIC-040G`, which lift the Grid
   types out of the shell when a second kind needs them.

Retire when: guard 1 never; guard 2's baseline file is deleted once it is empty, and
the check then stays as a plain ban.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from .boundaries.imports import resolve_relative, strip_prefix

_KIND_PACKAGES = (
    "modules.bots.application.kinds",
    "modules.bots.domain.grid",
)
_BASELINE_FILE = Path(__file__).with_name("baseline_bots_shell_imports_a_kind.txt")


def _repo_root() -> Path:
    """By landmark, not by hop count (`test_no_root_is_found_by_counting.py`)."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError("no pyproject.toml above this file")


_REPO_ROOT = _repo_root()
_SERVICES = _REPO_ROOT / "src" / "modules" / "bots" / "application" / "services"


def loose_top_level_files(entries: Iterable[Path]) -> list[str]:
    """Every file among the entries of `services`, other than a package marker."""
    return sorted(
        entry.name
        for entry in entries
        if entry.is_file() and entry.name != "__init__.py"
    )


def _imported_modules(tree: ast.Module, importing_module: str) -> set[str]:
    """Every module the file imports, relative imports resolved and the repository
    prefix stripped, as `boundaries/imports.py` does. `TYPE_CHECKING` blocks are
    read too: a shell type that names a kind still depends on it."""
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(strip_prefix(alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = resolve_relative(
                    importing_module, False, node.level, node.module
                )
            elif node.module:
                base = strip_prefix(node.module)
            else:
                continue
            modules.add(base)
            modules.update(f"{base}.{alias.name}" for alias in node.names)
    return modules


def _is_kind_module(module: str) -> bool:
    return any(
        module == package or module.startswith(f"{package}.")
        for package in _KIND_PACKAGES
    )


def files_importing_a_kind(paths: Iterable[Path], root: Path) -> list[str]:
    """Repo-relative paths of the given files that import a kind."""
    found = []
    for path in sorted(paths):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        dotted = ".".join(path.relative_to(root / "src").with_suffix("").parts)
        if any(_is_kind_module(m) for m in _imported_modules(tree, dotted)):
            found.append(path.relative_to(root).as_posix())
    return found


def _shell_files_importing_a_kind() -> list[str]:
    return files_importing_a_kind(_SERVICES.rglob("*.py"), _REPO_ROOT)


def _baseline() -> list[str]:
    return sorted(
        line.strip()
        for line in _BASELINE_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    )


def test_the_services_directory_holds_no_loose_file() -> None:
    loose = loose_top_level_files(_SERVICES.iterdir())

    assert loose == [], (
        "these files sit loose in `bots/application/services/`: "
        f"{loose}. Put each in the feature sub-package it belongs to (lifecycle, "
        "orders, venue, positions, risk, readiness, watches), or in "
        "`application/kinds/<kind>/` when it knows a kind (`BOT-177`)."
    )


def test_a_file_dropped_at_the_top_turns_the_loose_file_check_red(
    tmp_path: Path,
) -> None:
    package = tmp_path / "__init__.py"
    feature = tmp_path / "orders"
    package.write_text("", encoding="utf-8")
    feature.mkdir()
    assert loose_top_level_files([package, feature]) == []

    stray = tmp_path / "new_service.py"
    stray.write_text("", encoding="utf-8")

    assert loose_top_level_files([package, feature, stray]) == ["new_service.py"]


def test_no_new_shell_file_imports_a_kind() -> None:
    added = sorted(set(_shell_files_importing_a_kind()) - set(_baseline()))

    assert added == [], (
        "these shared-shell files import `application/kinds/` or `domain/grid/`: "
        f"{added}. A service every bot kind uses depends on no kind; move the file "
        "to `application/kinds/<kind>/`, or depend on a port in `contracts/`. Do "
        f"not add it to {_BASELINE_FILE.name}: that list only shrinks (`BOT-177`)."
    )


def test_the_baseline_lost_a_line_when_its_file_stopped_importing_a_kind() -> None:
    gone = sorted(set(_baseline()) - set(_shell_files_importing_a_kind()))

    assert gone == [], (
        f"these {_BASELINE_FILE.name} lines name files that no longer import a "
        f"kind (or no longer exist): {gone}. Delete them in the same commit."
    )


def test_probe_files_importing_a_kind_turn_the_direction_check_red(
    tmp_path: Path,
) -> None:
    feature = (
        tmp_path / "src" / "modules" / "bots" / "application" / "services" / "orders"
    )
    feature.mkdir(parents=True)
    clean = feature / "clean.py"
    clean.write_text(
        "from decimal import Decimal\nfrom ..lifecycle import bot_runner\n",
        encoding="utf-8",
    )
    assert files_importing_a_kind([clean], tmp_path) == []

    prefix = "Sagittarius_Elite_Warrior.src.modules.bots"
    for probe_name, source in {
        "kind_from.py": f"from {prefix}.application.kinds.grid.grid_facts import GridFacts\n",
        "kind_import.py": f"import {prefix}.application.kinds.grid\n",
        "domain_grid_from.py": f"from {prefix}.domain.grid.grid_plan import GridPlan\n",
        "domain_grid_package.py": f"from {prefix}.domain import grid\n",
        "relative_kind.py": "from ...kinds.grid import grid_facts\n",
        "relative_kind_module.py": "from ...kinds.grid.grid_facts import GridFacts\n",
        "relative_domain_grid.py": "from ....domain.grid.grid_plan import GridPlan\n",
    }.items():
        probe = feature / probe_name
        probe.write_text(source, encoding="utf-8")

        assert files_importing_a_kind([clean, probe], tmp_path) == [
            probe.relative_to(tmp_path).as_posix()
        ], probe_name


def test_the_guard_has_a_subject() -> None:
    assert (_SERVICES / "lifecycle").is_dir(), (
        f"{_SERVICES} has no `lifecycle/`: the shell moved, and this guard would "
        "pass over an empty scan"
    )
