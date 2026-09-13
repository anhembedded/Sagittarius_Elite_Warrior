"""
Every guard that scans a directory tree must be scanning a tree that exists
and is not empty (HLD §9.3 rule 4, ADR D18).

**Why.** A path-scanning guard computes its root from `Path(__file__)` and a
hand-counted `parents[N]`. Move the test file, rename the source directory,
or finish a migration phase that empties the old tree, and the guard scans
nothing, finds nothing, and passes — a green light with nobody at the gate.
`EPIC-025` moves both the source tree (`modules/`, `core/`, `support/`,
`shell/`) and the tests (`tests/unit/architecture/`), so this failure mode is
live for the whole migration.

**How.** `GUARDS` is the registry: each path-scanning test file in the
repository together with the directories it scans, relative to the repository
root. Three checks: (1) every registered guard file exists; (2) every registered
root exists and contains at least one file of the kind the guard reads;
(3) every test file that computes `Path(__file__).resolve().parents[` **and**
walks a directory (`glob`, `rglob`, `iterdir`) is registered here — a new guard must add its row, and a retargeted guard must
update its row, in the same commit.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.tests.unit.architecture.scanned_roots_registry import (
    GUARDS,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TESTS_ROOT = _REPO_ROOT / "tests"

_PARENTS_RE = re.compile(r"Path\(__file__\)\.resolve\(\)\.parents\[")
_SCAN_RE = re.compile(r"\.(?:rglob|glob|iterdir)\(")
#: Well below the 30 registered in Phase 0; fewer means the regexes broke.
_MINIMUM_GUARDS_EXPECTED = 20


def _registered_files() -> set[str]:
    return {guard for guard, _ in GUARDS}


def test_repo_root_is_where_we_think_it_is() -> None:
    assert (_REPO_ROOT / "src").is_dir() and (_REPO_ROOT / "tests").is_dir(), _REPO_ROOT


@pytest.mark.parametrize("guard", sorted(_registered_files()))
def test_registered_guard_file_exists(guard: str) -> None:
    assert (_REPO_ROOT / guard).is_file(), (
        f"registered guard is gone — update GUARDS: {guard}"
    )


@pytest.mark.parametrize(
    ("guard", "root", "pattern"),
    [(guard, root, pattern) for guard, roots in GUARDS for root, pattern in roots],
)
def test_scanned_root_exists_and_is_not_empty(
    guard: str, root: str, pattern: str
) -> None:
    directory = _REPO_ROOT / root
    assert directory.is_dir(), f"{guard} scans {root}, which does not exist"
    matches = [p for p in directory.rglob(pattern) if "__pycache__" not in p.parts]
    assert matches, (
        f"{guard} scans {root} for {pattern} and would find nothing — retarget the guard"
    )


def test_every_path_scanning_test_is_registered() -> None:
    """A test that computes `parents[N]` and walks a directory must have a row
    above. Tests that only use `parents[N]` for a `cwd` or a `sys.path` entry
    fail loudly on a wrong count, so they need no row."""
    found = set()
    for p in _TESTS_ROOT.rglob("test_*.py"):
        if "__pycache__" in p.parts:
            continue
        source = p.read_text(encoding="utf-8")
        if _PARENTS_RE.search(source) and _SCAN_RE.search(source):
            found.add(p.relative_to(_REPO_ROOT).as_posix())
    missing = sorted(found - _registered_files())
    assert missing == [], (
        "these tests compute a scan root from Path(__file__).parents[N] but are not\n"
        "registered in GUARDS (add a row naming the directories they scan):\n  "
        + "\n  ".join(missing)
    )
    assert len(found) >= 20, (
        "the regexes found suspiciously few guards; check _PARENTS_RE / _SCAN_RE"
    )
