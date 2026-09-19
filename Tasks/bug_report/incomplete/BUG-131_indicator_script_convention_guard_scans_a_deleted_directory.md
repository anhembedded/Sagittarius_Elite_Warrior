# BUG-131 — `test_every_script_is_registered_in_the_module` and the domain-UI-toolkit guard silently scan a directory `PR 1.6g` deleted

- **Reported:** 2026-09-19 (found while implementing `EPIC-025E` PR 4.4f-5 — moving indicator-script registration out of `src/binance_bot_module.py`)
- **Severity:** 🟢 P3 — no live defect reaches a user; the guard has simply stopped checking anything, which is a silent hole in coverage rather than a wrong answer shipped
- **Status:** Open
- **Environment:** Any — pure static analysis, no PySide6/qapp involved. Reproduced on `master-warrior` at `b58cc8d6` (2026-09-19), and present since `c3a949af` (2026-09-16, `EPIC-025` PR 1.6g).

## Reproduction

1. `python3 -c "from pathlib import Path; print(list(Path('src/domain/indicator_scripts').glob('*.py')) if Path('src/domain/indicator_scripts').exists() else 'MISSING')"` from the repo root — prints `MISSING`.
2. Run `tests/unit/support/indicators/test_indicator_script_conventions.py::test_every_script_is_registered_in_the_module` and `::test_domain_layer_never_imports_a_ui_toolkit` — both pass, every time, regardless of what indicator scripts exist or import.

Expected: a script defined but never registered, or a script importing `PySide6`/`pyqtgraph`, should fail one of these two tests. Actual: both tests vacuously pass because their scanned directory does not exist, so the set of things being checked is always empty.

## Symptom

`tests/unit/support/indicators/test_indicator_script_conventions.py`:
```python
_SCRIPTS_DIR = _BOT_ROOT / "src" / "domain" / "indicator_scripts"
_DOMAIN_DIR = _BOT_ROOT / "src" / "domain"
```
`src/domain/indicator_scripts/` does not exist — `ls src/domain/` shows only `value_objects/`. `_script_class_names()` (`_SCRIPTS_DIR.glob("*.py")`) therefore always returns `set()`, so `test_every_script_is_registered_in_the_module`'s `unregistered = sorted(set() - _registered_class_names())` is always `[]`. `test_domain_layer_never_imports_a_ui_toolkit` walks `_DOMAIN_DIR.rglob("*.py")`, which only reaches `src/domain/value_objects/*.py` — none of the actual indicator scripts.

The nine real indicator scripts live under `src/support/indicators/indicator_scripts/` (confirmed: `ls` lists `base_indicator_script.py`, `dev_indicator_script.py`, `ema_20/50/100/200_script.py`, `ema_cross_script.py`, `ema_ribbon_script.py`, `macd_full_script.py`, `rsi_14_script.py`) and are never read by either test.

## Root cause

`EPIC-025` PR 1.6g (`c3a949af4ffc099aa9cf5c3f3918980ff6a1c48e`, 2026-09-16) moved `domain/{indicators,indicator_scripts,scripting}` into `support/indicators`, and this test file itself moved from wherever it lived before into `tests/unit/support/indicators/` in the same commit — but `_SCRIPTS_DIR`/`_DOMAIN_DIR` (`test_indicator_script_conventions.py:32-33`) were never repointed at the new location, so the directory they name has not existed since that commit.

`tests/unit/architecture/scanned_roots_registry.py:229-240` already carries a **different**, seemingly-corrected claim for this same test file — `(("src/support/indicators/indicator_scripts", "*.py"), ("src/domain", "*.py"))`, with a comment explaining the second root is meant to "prove none has been left behind under `domain/`". That registry entry does not match what the test's own code actually reads (`src/domain/indicator_scripts`, not `src/support/indicators/indicator_scripts`) — whatever mechanism populated the registry row was never round-tripped back into the test file itself, or the registry entry was written aspirationally and the test never caught up. Not yet established which.

`tests/unit/architecture/test_module_domain_is_qt_free.py:54-57` already scans `support/indicators/indicator_scripts/**/*.py` (among other `support/indicators` sub-packages) for the same Qt-import prohibition, so `test_domain_layer_never_imports_a_ui_toolkit`'s check is now fully redundant with a correctly-targeted guard elsewhere — not a live gap for *that* specific property, only for `test_every_script_is_registered_in_the_module`'s registration check, which has no other guard covering it.

## Fix

Not yet implemented — deferred out of `EPIC-025E` PR 4.4f-5's bounded scope (that PR only needed to repoint `_MODULE_FILE`, which is a different constant in this same file, at the new location indicator-script *registration* moved to; it did not introduce or discover the `_SCRIPTS_DIR`/`_DOMAIN_DIR` staleness, it only surfaced it while reading the file). Candidate options, not evaluated in depth:
- Repoint `_SCRIPTS_DIR` to `src/support/indicators/indicator_scripts` and decide whether `_DOMAIN_DIR`'s Qt-toolkit check should retarget the same way or be deleted as redundant with `test_module_domain_is_qt_free.py`.
- Reconcile `scanned_roots_registry.py`'s entry with whatever the corrected test actually reads, and check whether `test_scanned_roots_are_not_empty.py` (or an equivalent meta-guard) would have caught this mismatch had one existed — if not, that meta-guard may need to verify a registered root is the one the test's own source actually names, not merely that the path glob happens to be non-empty.

## Regression test

Not yet written — belongs with the fix.

## Verification

Not run.

## Suggested next steps

- Confirm with `git blame`/`git log -p` on `c3a949af` whether the registry row was added in that same commit (aspirational from the start) or later (a sync pass that only updated the registry, not the test).
- Decide the retarget for `_SCRIPTS_DIR`/`_DOMAIN_DIR` and whether `test_domain_layer_never_imports_a_ui_toolkit` should be deleted rather than fixed, given `test_module_domain_is_qt_free.py` already covers the same property correctly.
- Update `scanned_roots_registry.py`'s row to match whatever the corrected test actually reads, in the same commit as the fix (`test_scanned_roots_are_not_empty.py`'s own contract).
