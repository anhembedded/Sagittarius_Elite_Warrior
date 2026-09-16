# CS-004 — the tests the gate never ran

`BUG-128`: the time-range picker opened on an **inverted** range (`08 Jul → 01 Jul`) and let the
user Apply it, which the backend reads as an empty window. `refresh()` detected the state and
declined to repair it: `if start is None or end is None or start > end:` filled gaps with
`end = end or now` / `start = start or (end - week)`, and for the third disjunct both values are
non-`None`, so both `or`s keep what they had.

## Why nothing caught it

| Net | Why it was silent | Still open? |
| :--- | :--- | :--- |
| the subject's own 13 unit tests | they lived beside it **under `src/`**, and the gate runs `pytest Sagittarius_Elite_Warrior/tests` — collected by nobody, on any run. PR 1.4b-2 found this and counted them; this is the first time it cost anything | **yes — 22 files** |
| the same 13, read as source | they cover the *unparseable* branch and never `start > end`; a three-disjunct condition with two covered reads as covered | yes, wherever a condition names more states than its tests enter |
| the host test citing them | its docstring called them *"full coverage with no `QApplication` at all"* — true about a file, false about the gate | yes |
| `can_apply` | it asks whether both ends are present, which an inverted pair satisfies; ordering was never its question | no — one producer |

## The fix

- `seed_range()` in `src/support/ui_kit/time_range_picker/range_rules.py` is **three explicit
  branches** instead of one condition plus fallbacks; inverted keeps the end and re-derives the
  start. The bug *was* a fallback that missed the case its own condition named.
- `tests/unit/architecture/test_no_test_file_lives_under_src.py` — **new**: no `test_*.py`,
  `*_test.py` or `conftest.py` under `src/`, against a shrink-only baseline of 22. A new one fails
  at once; the 22 sit in QML packages ADR D21 deletes, so the list reaches zero with the last `.qml`.
- The rules now have a suite the gate does run: `tests/unit/support/ui_kit/time_range_picker/`,
  14 tests including the inverted case, confirmed red before the fix.

## Where else this is still open

- **22 files** under `src/**/tests/` are still unrunnable, one set per surviving QML package.
- Any docstring citing coverage by **location** rather than by a gate run makes the same claim.
- `src/presentation/` is outside mypy wholesale — typing and arithmetic both unwatched there until a
  file leaves it (PR 2.1e and PR 4.1b each found a real type error that way).
