"""A `src/` or `tests/` file already over the 400-line ceiling never grows further.

**The gap this closes.** `architecture-rule.md` §5.4 sets a hard split
threshold — **>400 lines per file** — but enforcement was review-only
(`[review: C7, D6, D7]`): nothing stopped a file already over the ceiling
from growing further. `BOT-144`'s independent PR review named exactly this
gap for `src/`. `BOT-146` extended the guard to `tests/`, after the reviews of
PR #294 and PR #295 each found a test file that had grown past the ceiling: a
finding that recurs needs a guard, not another split.

**One baseline per tree** (`baseline_god_files.json` for `src/`,
`baseline_test_god_files.json` for `tests/`), and every check below runs once
per tree.

**Two different failure modes, on purpose.** A file already in its tree's
baseline may shrink freely but never grow past its recorded count — that is
the ratchet, mirroring `test_app_styling_only_shrinks.py`. A file crossing 400
lines for the **first time** is not offered that same path: this rule's own
remedy is to split the file, not to grandfather it in, so a brand-new
violation fails outright with an instruction to split, never a suggestion to
add a baseline entry. Unlike the styling census (legitimate, reversible
per-widget edits), a line-count baseline entry that could always be padded
back up to "make room" would defeat the ratchet's purpose.

Retire when: every `src/` and `tests/` file is at or under 400 lines and both
baselines are empty — at that point this guard and `architecture-rule.md`
§5.4's file-length threshold can both become a plain hard ceiling with no
baseline at all.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.tools.measure_god_files import (
    LINE_CEILING,
    MEASURED_ROOTS,
    measure,
)

_BASELINE_FILES = {
    "src": Path(__file__).with_name("baseline_god_files.json"),
    "tests": Path(__file__).with_name("baseline_test_god_files.json"),
}


def _baseline(root: str) -> dict[str, int]:
    return json.loads(_BASELINE_FILES[root].read_text(encoding="utf-8"))


def test_every_measured_tree_has_a_baseline() -> None:
    assert set(_BASELINE_FILES) == set(MEASURED_ROOTS)


@pytest.mark.parametrize("root", MEASURED_ROOTS)
def test_known_god_files_do_not_grow(root: str) -> None:
    measured = measure(root)
    grown = {
        path: (baseline_lines, measured[path])
        for path, baseline_lines in _baseline(root).items()
        if path in measured and measured[path] > baseline_lines
    }
    assert not grown, (
        f"these {root}/ files already over the {LINE_CEILING}-line ceiling "
        f"grew further (baseline -> measured): {grown}. Split the added code "
        "out instead of letting the file grow (architecture-rule.md §5.4)."
    )


@pytest.mark.parametrize("root", MEASURED_ROOTS)
def test_no_new_god_files_appear(root: str) -> None:
    baseline = _baseline(root)
    new_violations = {
        path: lines for path, lines in measure(root).items() if path not in baseline
    }
    assert not new_violations, (
        f"these {root}/ files newly exceed the {LINE_CEILING}-line ceiling: "
        f"{new_violations}. Split them (architecture-rule.md §5.4) rather than "
        f"adding an entry to {_BASELINE_FILES[root].name}: that file tracks "
        "only debt that predates this guard, not a place to register new debt."
    )


@pytest.mark.parametrize("root", MEASURED_ROOTS)
def test_baseline_entries_still_exceed_the_ceiling(root: str) -> None:
    measured = measure(root)
    stale = {
        path: baseline_lines
        for path, baseline_lines in _baseline(root).items()
        if path not in measured
    }
    assert not stale, (
        f"these {_BASELINE_FILES[root].name} entries no longer exceed the "
        f"{LINE_CEILING}-line ceiling (shrunk under it, moved, or were "
        f"deleted): {stale}. Remove them from the baseline in the same "
        "commit that fixed them — a ratchet that is never tightened stops "
        "being one."
    )
