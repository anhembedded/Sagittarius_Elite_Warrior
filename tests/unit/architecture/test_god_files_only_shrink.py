"""A `src/` file already over the 400-line ceiling never grows further.

**The gap this closes.** `architecture-rule.md` §5.4 sets a hard split
threshold — **>400 lines per file** — but enforcement was review-only
(`[review: C7, D6, D7]`): nothing stopped a file already over the ceiling
from growing further. `BOT-144`'s independent PR review named exactly this
gap ("no guard test currently catches this").

**Two different failure modes, on purpose.** A file already in
`baseline_god_files.json` may shrink freely but never grow past its recorded
count — that is the ratchet, mirroring `test_app_styling_only_shrinks.py`.
A file crossing 400 lines for the **first time** is not offered that same
path: this rule's own remedy is to split the file, not to grandfather it in,
so a brand-new violation fails outright with an instruction to split, never
a suggestion to add a baseline entry. Unlike the styling census (legitimate,
reversible per-widget edits), a line-count baseline entry that could always
be padded back up to "make room" would defeat the ratchet's purpose.

**Scope is `src/` only** (`tools/measure_god_files.py`'s own docstring says
why) — `tests/`/`tools/` also exceed 400 lines in many places, deliberately
left to a future task rather than folded in here.

Retire when: every `src/` file is at or under 400 lines and
`baseline_god_files.json` is empty — at that point this guard and
`architecture-rule.md` §5.4's file-length threshold can both become a plain
hard ceiling with no baseline at all.
"""

from __future__ import annotations

import json
from pathlib import Path

from Sagittarius_Elite_Warrior.tools.measure_god_files import LINE_CEILING, measure

_BASELINE_FILE = Path(__file__).with_name("baseline_god_files.json")
_MEASURED = measure()
_BASELINE: dict[str, int] = json.loads(_BASELINE_FILE.read_text(encoding="utf-8"))


def test_known_god_files_do_not_grow() -> None:
    grown = {
        path: (baseline_lines, _MEASURED[path])
        for path, baseline_lines in _BASELINE.items()
        if path in _MEASURED and _MEASURED[path] > baseline_lines
    }
    assert not grown, (
        "these src/ files already over the 400-line ceiling grew further "
        f"(baseline -> measured): {grown}. Split the added code out instead "
        "of letting the file grow (architecture-rule.md §5.4)."
    )


def test_no_new_god_files_appear() -> None:
    new_violations = {
        path: lines for path, lines in _MEASURED.items() if path not in _BASELINE
    }
    assert not new_violations, (
        f"these src/ files newly exceed the {LINE_CEILING}-line ceiling: "
        f"{new_violations}. Split them (architecture-rule.md §5.4) rather than "
        "adding an entry to baseline_god_files.json — that file tracks only "
        "debt that predates this guard, not a place to register new debt."
    )


def test_baseline_entries_still_exceed_the_ceiling() -> None:
    stale = {
        path: baseline_lines
        for path, baseline_lines in _BASELINE.items()
        if path not in _MEASURED
    }
    assert not stale, (
        "these baseline_god_files.json entries no longer exceed the "
        f"{LINE_CEILING}-line ceiling (shrunk under it, moved, or were "
        f"deleted): {stale}. Remove them from the baseline in the same "
        "commit that fixed them — a ratchet that is never tightened stops "
        "being one."
    )
