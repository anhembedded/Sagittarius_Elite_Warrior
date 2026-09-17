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

import re
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
#:
#: **`application` was retired from this list on 2026-09-17, not loosened out of
#: it.** `EPIC-025` emptied `src/application/` — PR 2.1c-2 took the last event
#: handler and PR 3.1c the last use case — so the directory is gone from the
#: repository by design, and a list that demands it would fail every fresh
#: clone. It did not fail *anyone* for a month, which is `BUG-129`: every
#: working tree kept the directory alive as a `__pycache__` shell, and GitHub
#: CI never reached pytest because the reference checker ahead of it was
#: already red. The rule below is untouched — it scans `src` whole, and
#: `_MINIMUM_SCANNED_FILES` is what catches a wrong tree.
#:
#: `domain` is next: it holds exactly one file (`value_objects/market_type.py`),
#: and the pull request that moves it must drop this entry in the same commit.
#: `LEGACY_ZONES` keeps both names on purpose — a zone with no files classifies
#: nothing, while the rule table still has to know what a legacy zone *is*.
_ZONES_THAT_MUST_EXIST = ("domain", "presentation", "infrastructure")
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


#: Where the allowlist narrates its count, and where that narration ends: the
#: sentence begins at `_HISTORY_OPENS` and runs to the next blank comment line.
#: Slicing first, then matching, is the difference between "the last figure in
#: the history sentence" — which is what this guard means — and "the last figure
#: anywhere in the file", which is what it did until the review of PR 2.1a. The
#: file has eight `N after PR` matches today and all eight are inside the
#: sentence, so the looser version happened to agree; a later comment mentioning
#: one would have made the guard compare a number nobody claimed.
_HISTORY_OPENS = "History of the count:"
_HISTORY_ENDS = "\n#\n"

#: Every `N after PR <id>` inside that slice. The **last** one is the file's
#: current claim. Matched as a list rather than by anchoring on the end of the
#: sentence, because "PR 0.3" contains a full stop and a pattern that ended at
#: one read the *first* figure instead of the last — which this guard caught on
#: its first run, against itself.
_HISTORY_COUNT = re.compile(r"(\d+)\s+after\s+PR\s")


def _documented_count(header: str) -> int | None:
    """The last figure the allowlist's history sentence claims, or `None` when
    the sentence is not there to read."""
    if _HISTORY_OPENS not in header:
        return None
    sentence = header.split(_HISTORY_OPENS, 1)[1].split(_HISTORY_ENDS, 1)[0]
    figures = _HISTORY_COUNT.findall(sentence)
    return int(figures[-1]) if figures else None


def test_the_documented_count_is_the_real_count() -> None:
    """The allowlist header narrates its own count, and that sentence is the
    number every board and tracking row quotes. It does not update itself.

    It went stale for eleven pull requests — the header said 56 while the file
    held 23 — and on 2026-09-16 a *third* figure, 36, was read out of
    `Tasks/epics/README.md` and copied into six tracking rows and a decision
    record in one day, as "unchanged at 36". 36 is a number this file has never
    held. Nothing was watching, because a count in prose is not checkable
    unless something checks it, which is what
    `.agents/Skills/README.md` section 1 means by banning a count written into a
    briefing as current state.

    So: the last figure in the history sentence must equal the entries below it.
    A pull request that adds or retires one edits that line in the same commit,
    and every document quoting the number has one place to copy from.
    """
    documented = _documented_count(_ALLOWLIST_FILE.read_text(encoding="utf-8"))

    assert documented is not None, (
        f"the allowlist header no longer carries a {_HISTORY_OPENS!r} sentence "
        "ending in 'N after PR X'. It is what every board quotes; restore it, or "
        "retarget this guard at whatever replaced it."
    )

    real = len(read_allowlist(_ALLOWLIST_FILE))

    assert documented == real, (
        f"the allowlist header says its history ends at {documented} entries; it "
        f"holds {real}. Update the last figure on that line in the commit that "
        "changed the entries — a stale one gets copied into the boards, which is "
        "exactly how 36 (a count this file never held) reached six tracking rows "
        "and a decision record on 2026-09-16."
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
