"""Inside one module, dependencies point inward (`architecture-rule.md` §3).

**Why this guard exists** (`EPIC-030E`). `test_module_boundaries.py` governs
imports *between* zones; for two files of the same module
`rules.import_is_allowed` returns `True` before asking anything
(`boundaries/rules.py`, `src_zone == dst_zone`). So `modules.x.domain`
importing `modules.x.ui` — the exact inversion §3 forbids — has passed every
gate since the module tree was born. The 2026-10-04 audit measured one such
import (recorded in `allowlist_module_layers.txt`) and nothing guarding the
direction.

**The rule** (`boundaries/layers.py`): `domain` imports no `application`,
`adapters`, `ui`, `composition`, `cli` or `module.py` of its own module;
`application` none of the outer four plus `module.py`; `contracts` none of
`application` or the outer layers. `contracts → domain` stays allowed (the
documented decision in `strategy/contracts/i_sizing_policy.py`). Function-
local imports count; `TYPE_CHECKING` imports do not (`boundaries/imports.py`).

**The ratchet** is `test_module_boundaries.py`'s: a pair not in the allowlist
fails, a listed pair that no longer exists fails. It only shrinks.

Retire when: `boundaries/rules.py` itself refuses outward imports inside a
module (this file's rule folded into the zone policy), so one guard answers
both questions.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.tests.unit.architecture.boundaries.allowlist import (
    Violation,
    read_allowlist,
)
from Sagittarius_Elite_Warrior.tests.unit.architecture.boundaries.imports import (
    imported_modules,
)
from Sagittarius_Elite_Warrior.tests.unit.architecture.boundaries.layers import (
    layer_import_is_allowed,
)
from Sagittarius_Elite_Warrior.tests.unit.architecture.boundaries.scan import (
    find_layer_violations,
    module_name,
    scanned_files,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_ROOT = _REPO_ROOT / "src"
_ALLOWLIST_FILE = Path(__file__).with_name("allowlist_module_layers.txt")

#: Measured 2026-10-04: 2,374 imports between two files of one module. The
#: floor catches a scan that lost its subject, not churn.
_MIN_INTRA_MODULE_IMPORTS = 200


def _render(violations: list[Violation]) -> str:
    return "\n".join(f"  {v.as_line()}" for v in violations)


def _intra_module_imports() -> list[Violation]:
    """Every import between two files of one module — what this guard rules
    on, counted so an empty scan cannot pass silently."""
    found: list[Violation] = []
    for py_file in scanned_files(_SRC_ROOT):
        importing, is_package = module_name(_SRC_ROOT, py_file)
        if not importing.startswith("modules."):
            continue
        prefix = ".".join(importing.split(".")[:2]) + "."
        source = py_file.read_text(encoding="utf-8")
        found.extend(
            Violation(importing, imported)
            for imported in imported_modules(importing, source, is_package=is_package)
            if imported.startswith(prefix)
        )
    return found


def test_the_scan_sees_imports_inside_modules() -> None:
    imports = _intra_module_imports()
    assert len(imports) > _MIN_INTRA_MODULE_IMPORTS, (
        f"only {len(imports)} intra-module imports under {_SRC_ROOT}/modules — "
        "the tree moved or the reader went blind"
    )
    importing_layers = {v.importing_module.split(".")[2] for v in imports}
    assert {"domain", "application", "contracts"} <= importing_layers


def test_no_layer_imports_outward_beyond_the_allowlist() -> None:
    allowed = set(read_allowlist(_ALLOWLIST_FILE))
    new_violations = [v for v in find_layer_violations(_SRC_ROOT) if v not in allowed]
    assert new_violations == [], (
        "a module's inner layer imports an outer layer of the same module.\n"
        "Invert it: a port in the inner layer, the implementation outside, wired\n"
        "in composition/. The allowlist only shrinks, it never grows.\n\n"
        + _render(new_violations)
    )


def test_the_allowlist_has_not_gone_stale() -> None:
    actual = set(find_layer_violations(_SRC_ROOT))
    stale = sorted(set(read_allowlist(_ALLOWLIST_FILE)) - actual)
    assert stale == [], (
        "allowlist entries no longer correspond to an existing import — delete them:\n"
        + _render(stale)
    )


def test_the_allowlist_has_no_duplicate_entries() -> None:
    entries = read_allowlist(_ALLOWLIST_FILE)
    assert len(entries) == len(set(entries)), "duplicate lines in the allowlist"


# --- probes: the guard can fail -------------------------------------------


def _violations_in(importing: str, source: str) -> list[str]:
    return sorted(
        imported
        for imported in imported_modules(importing, source)
        if not layer_import_is_allowed(importing, imported)
    )


def test_a_domain_file_importing_its_own_ui_is_refused() -> None:
    source = (
        "from Sagittarius_Elite_Warrior.src.modules.trading.ui.panel import Panel\n"
    )
    assert _violations_in("modules.trading.domain.order", source) == [
        "modules.trading.ui.panel"
    ]


def test_a_function_local_outward_import_is_refused() -> None:
    """The one entry in the allowlist is exactly this shape: lazy, and still
    an outward dependency."""
    source = (
        "def build():\n"
        "    from Sagittarius_Elite_Warrior.src.modules.trading.adapters.x import X\n"
    )
    assert _violations_in("modules.trading.application.services.s", source) == [
        "modules.trading.adapters.x"
    ]


def test_a_relative_outward_import_is_refused() -> None:
    source = "from ...ui.panel import Panel\n"
    assert _violations_in("modules.trading.application.services.s", source) == [
        "modules.trading.ui.panel"
    ]


def test_a_type_checking_outward_import_is_allowed() -> None:
    source = (
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from Sagittarius_Elite_Warrior.src.modules.trading.ui.panel import Panel\n"
    )
    assert _violations_in("modules.trading.domain.order", source) == []


@pytest.mark.parametrize(
    "allowed_line",
    [
        "from Sagittarius_Elite_Warrior.src.modules.trading.domain.order import Order\n",
        "from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_x import IX\n",
        # another module's ui is the zone policy's question, not this one's
        "from Sagittarius_Elite_Warrior.src.modules.strategy.ui.panel import Panel\n",
    ],
)
def test_inward_and_cross_module_imports_are_not_this_guards_business(
    allowed_line: str,
) -> None:
    assert _violations_in("modules.trading.application.services.s", allowed_line) == []
