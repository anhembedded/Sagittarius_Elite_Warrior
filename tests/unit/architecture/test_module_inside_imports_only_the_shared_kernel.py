"""A module's inside imports nothing from the Engine but the Shared Kernel
(`architecture-rule.md` §3).

**Why this guard exists** (`EPIC-030D`). The rule's tag pointed at
`test_indicator_script_conventions.py`, whose allow-list scans the indicator
scripts and nothing else. The 2026-10-04 audit found what that left open:
`modules/strategy/application/services/live_strategy_config_store.py` imported
the Engine's `IConfig` — a live breach in exactly the layer the rule names,
and no test that could see it. The fix routed it through the application's
own `IConfigReader`/`IConfigWriter`; this file is what keeps the next one out.

**The rule.** Under `src/modules/*/{domain,application,contracts}/`, every
runtime import rooted at `sagittarius_engine` must be one of
`SHARED_KERNEL_MODULES` (`boundaries/rules.py`: `BaseEvent`, `IDomainEvent`).
Function-local imports count — a lazy import still runs. Imports inside
`if TYPE_CHECKING:` do not: a type name costs no runtime dependency
(`boundaries/imports.runtime_nodes`, the same walker the Qt-free guard uses).
`adapters/`, `ui/`, `composition/` and `module.py` are outside the rule on
purpose: they are where the Engine is allowed in.

Retire when: the Engine's Shared Kernel and the module tree stop being
separate packages (not planned), or `architecture-rule.md` §3 drops the
Shared Kernel rule.
"""

from __future__ import annotations

import ast
from pathlib import Path

from Sagittarius_Elite_Warrior.tests.unit.architecture.boundaries.imports import (
    runtime_nodes,
)
from Sagittarius_Elite_Warrior.tests.unit.architecture.boundaries.rules import (
    SHARED_KERNEL_MODULES,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MODULES_ROOT = _REPO_ROOT / "src" / "modules"

_ENGINE_ROOT = "sagittarius_engine"

#: Measured 2026-10-04: 400+ files across four modules. The floor is far
#: below that on purpose — it catches a glob that lost its subject, not churn.
_MIN_FILES_SCANNED = 100


def _inside_files() -> list[Path]:
    """Every `.py` file in a module's domain, application or contracts layer.
    Three literal globs, so `guard_scan_resolver.py` can follow them."""
    found = {
        *_MODULES_ROOT.glob("*/domain/**/*.py"),
        *_MODULES_ROOT.glob("*/application/**/*.py"),
        *_MODULES_ROOT.glob("*/contracts/**/*.py"),
    }
    return sorted(path for path in found if "__pycache__" not in path.parts)


def _runtime_engine_imports(source: str) -> list[tuple[int, str]]:
    """`(line, module)` for every runtime import rooted at the Engine."""
    found: list[tuple[int, str]] = []
    for node in runtime_nodes(ast.parse(source)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names = [node.module]
        else:
            continue
        found.extend(
            (node.lineno, name) for name in names if name.split(".")[0] == _ENGINE_ROOT
        )
    return found


def engine_imports_outside_the_kernel(source: str) -> list[tuple[int, str]]:
    """The runtime Engine imports `source` makes that are not Shared Kernel."""
    return [
        (line, module)
        for line, module in _runtime_engine_imports(source)
        if module not in SHARED_KERNEL_MODULES
    ]


# --------------------------------------------------------------------------- #
# The tree                                                                    #
# --------------------------------------------------------------------------- #


def test_the_scan_reaches_every_layer_it_governs() -> None:
    """A guard that scans nothing passes everything (HLD §9.3 rule 4). Each of
    the three layers must contribute, and the Shared Kernel must actually be
    seen in use — otherwise the allowance below is untested against reality."""
    files = _inside_files()
    assert len(files) > _MIN_FILES_SCANNED, (
        f"only {len(files)} files under {_MODULES_ROOT}/*/{{domain,application,"
        "contracts}} — the globs or the tree moved"
    )
    layers = {path.relative_to(_MODULES_ROOT).parts[1] for path in files}
    assert layers == {"domain", "application", "contracts"}
    kernel_uses = [
        module
        for path in files
        for _line, module in _runtime_engine_imports(path.read_text(encoding="utf-8"))
        if module in SHARED_KERNEL_MODULES
    ]
    assert "sagittarius_engine.domain.base_event" in kernel_uses


def test_no_module_inside_imports_the_engine_beyond_the_shared_kernel() -> None:
    offenders = [
        f"  {path.relative_to(_REPO_ROOT).as_posix()}:{line}  {module}"
        for path in _inside_files()
        for line, module in engine_imports_outside_the_kernel(
            path.read_text(encoding="utf-8")
        )
    ]
    assert offenders == [], (
        "a module's domain/application/contracts imports the Engine beyond the\n"
        "Shared Kernel (`BaseEvent`, `IDomainEvent`). Depend on a port in\n"
        "`src/core/contracts/` (`IConfigReader`, `IEventPublisher`, ...) and let\n"
        "the composition root bind the Engine-backed adapter:\n" + "\n".join(offenders)
    )


# --------------------------------------------------------------------------- #
# Probes: the guard can fail                                                  #
# --------------------------------------------------------------------------- #


def test_an_engine_port_import_is_flagged() -> None:
    source = "from sagittarius_engine.interfaces.i_config import IConfig\n"
    assert engine_imports_outside_the_kernel(source) == [
        (1, "sagittarius_engine.interfaces.i_config")
    ]


def test_a_plain_engine_import_is_flagged() -> None:
    assert engine_imports_outside_the_kernel("import sagittarius_engine\n") == [
        (1, "sagittarius_engine")
    ]


def test_a_function_local_engine_import_is_flagged() -> None:
    """A lazy import is still a runtime dependency."""
    source = (
        "def build():\n"
        "    from sagittarius_engine.interfaces.i_event_bus import IEventBus\n"
        "    return IEventBus\n"
    )
    assert engine_imports_outside_the_kernel(source) == [
        (2, "sagittarius_engine.interfaces.i_event_bus")
    ]


def test_the_shared_kernel_is_allowed() -> None:
    source = (
        "from sagittarius_engine.domain.base_event import BaseEvent\n"
        "from sagittarius_engine.domain.i_domain_event import IDomainEvent\n"
    )
    assert engine_imports_outside_the_kernel(source) == []


def test_a_sibling_of_the_kernel_is_not_allowed() -> None:
    """Exact module paths, never a prefix: the package the kernel lives in is
    not itself the kernel."""
    source = "from sagittarius_engine.domain import base_event\n"
    assert engine_imports_outside_the_kernel(source) == [
        (1, "sagittarius_engine.domain")
    ]


def test_a_type_checking_engine_import_is_allowed() -> None:
    source = (
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from sagittarius_engine.interfaces.i_config import IConfig\n"
    )
    assert engine_imports_outside_the_kernel(source) == []


def test_imports_outside_the_engine_are_ignored() -> None:
    source = (
        "import logging\n"
        "from Sagittarius_Elite_Warrior.src.core.contracts.i_config_reader import (\n"
        "    IConfigReader,\n"
        ")\n"
        "from . import sibling\n"
    )
    assert engine_imports_outside_the_kernel(source) == []
