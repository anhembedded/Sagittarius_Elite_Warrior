"""
Import boundaries between the layers of the legacy tree and, as they appear,
between the bounded-context modules of `EPIC-025` (HLD §6.1, ADR D1 / D4).

**Why this guard exists.** `architecture-rule.md` §3 has forbidden
`application → infrastructure` since the rule was written, and five command
handlers import `FuturesTradingClient` anyway (HLD §7.3 measured it with two
independent tools). A rule nobody executes is a wish. This file executes it.

**How the ratchet works.** `allowlist_module_boundaries.txt` next to this file
records every violation *as found* when the guard was first run. Two things
fail the test:

1. a pair that is **not** in the allowlist — a new violation;
2. a pair in the allowlist that **no longer** exists — the fix landed, so the
   entry must be deleted in the same commit. Shrinking is mandatory; the list
   never records a decision that is already history.

Entries are removed by `EPIC-025B` … `EPIC-025E`; the list is empty when
Phase 4 closes (HLD §6.2).

**Where the pieces live** (`boundaries/`, one abstraction level per file):
`zones.py` names the zones, `rules.py` is the policy, `imports.py` reads a
file's imports, `allowlist.py` reads the ratchet file, `scan.py` walks the
tree. `test_boundary_rules.py` pins the policy table;
`test_boundary_import_collection.py` proves the reader sees what it should.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.tests.unit.architecture.boundaries.allowlist import (
    Violation,
    read_allowlist,
)
from Sagittarius_Elite_Warrior.tests.unit.architecture.boundaries.imports import (
    imported_modules,
)
from Sagittarius_Elite_Warrior.tests.unit.architecture.boundaries.scan import (
    find_violations,
    module_name,
    scanned_files,
)
from Sagittarius_Elite_Warrior.tests.unit.architecture.boundaries.zones import (
    LEGACY_ZONES,
    zone_of,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_ROOT = _REPO_ROOT / "src"
_ALLOWLIST_FILE = Path(__file__).with_name("allowlist_module_boundaries.txt")
_SHELL_LEGACY_FILE = Path(__file__).with_name("baseline_shell_legacy_imports.txt")

#: Zones that must exist for this guard to be scanning the tree it thinks it is.
_ZONES_THAT_MUST_EXIST = ("domain", "application", "presentation", "infrastructure")
#: Well below the real count (about 600); a scan that finds fewer is scanning
#: the wrong directory.
_MINIMUM_SCANNED_FILES = 100


def _render(violations: list[Violation]) -> str:
    return "\n".join(f"  {v.as_line()}" for v in violations)


def test_src_root_is_where_we_think_it_is() -> None:
    """`parents[3]` is a hand-computed path. One level off and every test below
    scans an empty directory and passes — the vacuous-guard failure HLD §9.3
    rule 4 forbids."""
    assert _SRC_ROOT.is_dir(), f"no src tree at {_SRC_ROOT}"
    for zone in _ZONES_THAT_MUST_EXIST:
        assert (_SRC_ROOT / zone).is_dir(), f"zone `{zone}` missing under {_SRC_ROOT}"
    assert len(scanned_files(_SRC_ROOT)) > _MINIMUM_SCANNED_FILES


def test_no_import_crosses_a_boundary_outside_the_allowlist() -> None:
    allowed = set(read_allowlist(_ALLOWLIST_FILE))
    new_violations = [v for v in find_violations(_SRC_ROOT) if v not in allowed]
    assert new_violations == [], (
        "an import crosses a layer or module boundary that the allowlist does not\n"
        "record. Fix the direction (a port in the importing layer, an adapter in\n"
        "the outer one) — the allowlist only shrinks, it never grows.\n\n"
        + _render(new_violations)
    )


def test_the_allowlist_has_not_gone_stale() -> None:
    """An allowlist that outlives the violation it excuses stops being a record
    of a decision and becomes a place to hide. When a phase removes an import,
    this test goes red and forces the entry out in the same commit."""
    actual = set(find_violations(_SRC_ROOT))
    stale = sorted(set(read_allowlist(_ALLOWLIST_FILE)) - actual)
    assert stale == [], (
        "allowlist entries no longer correspond to an existing import — delete them:\n"
        + _render(stale)
    )


def test_the_allowlist_has_no_duplicate_entries() -> None:
    entries = read_allowlist(_ALLOWLIST_FILE)
    assert len(entries) == len(set(entries)), "duplicate lines in the allowlist"


# --- the shell's own permission, kept finite ------------------------------


def _shell_imports_of_the_legacy_tree() -> list[Violation]:
    """Every legacy module the shell imports. Allowed by `rules.py` because the
    shell is *Main*; recorded here so the permission cannot quietly spread."""
    found: list[Violation] = []
    for py_file in scanned_files(_SRC_ROOT):
        importing, is_package = module_name(_SRC_ROOT, py_file)
        if zone_of(importing) != "shell":
            continue
        source = py_file.read_text(encoding="utf-8")
        for imported in imported_modules(importing, source, is_package=is_package):
            if zone_of(imported) in LEGACY_ZONES:
                found.append(Violation(importing, imported))
    return sorted(set(found))


def test_the_shell_imports_no_new_part_of_the_legacy_tree() -> None:
    recorded = set(read_allowlist(_SHELL_LEGACY_FILE))
    added = [v for v in _shell_imports_of_the_legacy_tree() if v not in recorded]
    assert added == [], (
        "the shell reaches into the legacy tree somewhere new. Main may wire what\n"
        "exists, but this list does not grow: put the code behind a core/ contract,\n"
        "or wire it from shell/composition_root.py, which is the composition root.\n\n"
        + _render(added)
    )


def test_the_shell_legacy_baseline_has_not_gone_stale() -> None:
    actual = set(_shell_imports_of_the_legacy_tree())
    gone = sorted(set(read_allowlist(_SHELL_LEGACY_FILE)) - actual)
    assert gone == [], (
        "these shell imports of the legacy tree are gone — delete their lines:\n"
        + _render(gone)
    )
