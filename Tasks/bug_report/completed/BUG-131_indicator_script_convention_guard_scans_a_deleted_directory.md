# BUG-131 — `test_every_script_is_registered_in_the_module` and the domain-UI-toolkit guard silently scan a directory `PR 1.6g` deleted

- **Reported:** 2026-09-19 (found while implementing `EPIC-025E` PR 4.4f-5 — moving indicator-script registration out of `src/binance_bot_module.py`)
- **Severity:** 🟢 P3 — no live defect reaches a user; the guard has simply stopped checking anything, which is a silent hole in coverage rather than a wrong answer shipped
- **Status:** ✅ Fixed (2026-09-19)
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

`tests/unit/architecture/test_module_domain_is_qt_free.py:54-57` already scans `support/indicators/indicator_scripts/**/*.py` for a runtime `PySide6`/`PyQt5`/`PyQt6`/`pyqtgraph`/`sagittarius_engine.extensions.pyside_mvc` import — **correction to the original report's claim above**: this does *not* make `test_domain_layer_never_imports_a_ui_toolkit` fully redundant. That guard's `_FORBIDDEN_DOMAIN_IMPORTS` bans the whole `sagittarius_engine` package (with the two-symbol `_SHARED_KERNEL_MODULES` exception), not only its `pyside_mvc` extension — `architecture-rule.md` §3 ("Layers") names this exact test file (`tests/unit/support/indicators/test_indicator_script_conventions.py allow-list`) as the sole enforcement of that Shared Kernel allow-list, and nothing else scans `support/indicators/indicator_scripts` for a bare `sagittarius_engine` import. With `_DOMAIN_DIR` pointing at the deleted tree, that allow-list was unenforced for indicator scripts since PR 1.6g, not merely duplicated.

## Fix

`tests/unit/support/indicators/test_indicator_script_conventions.py`: retargeted `_SCRIPTS_DIR` to `src/support/indicators/indicator_scripts` (where PR 1.6g actually left the scripts) and `_DOMAIN_DIR` to the same tree — it never needed a separate "domain" root; the property it checks (the Shared Kernel allow-list) belongs to the indicator scripts, not to a `src/domain` package that no longer exists here. Added `test_there_are_scripts_and_a_domain_tree_to_check`, mirroring `test_module_domain_is_qt_free.py`'s own `test_there_are_qt_free_packages_to_check` pattern, so a future retarget that loses its subject fails loudly instead of passing vacuously again.

`tests/unit/architecture/scanned_roots_registry.py`: removed the stale `("src/domain", "*.py")` row (the test no longer reads it) and left the one row that already matched.

Not fixed here, and explicitly out of this bug's bounded scope: `test_scanned_roots_are_not_empty.py` verifies a registered root *exists and is non-empty*, but never verifies a guard's own source actually reads the path registered for it — this registry already carried the *correct* path for this guard while the guard's code read a different, wrong one, and the meta-guard had no way to notice. Closing that generally means parsing each guard's own path-construction expressions and is a change to a mechanism ~30 other guards share; disproportionate to fix under a P3 report about one guard's stale constants. Filed as a follow-up task instead of silently dropped (see Suggested next steps below at time of filing; a task suggestion was queued from this session).

## Regression test

`tests/unit/support/indicators/test_indicator_script_conventions.py::test_there_are_scripts_and_a_domain_tree_to_check` — confirmed failing beforehand (`AssertionError: no scripts found under .../src/domain/indicator_scripts`), passes after the retarget. Positive proof the repaired mechanism runs, not just the absence of the symptom: `_script_class_names()` now finds the real 9 concrete `BaseIndicatorScript` subclasses (`DevIndicatorScript`, `Ema20/50/100/200Script`, `EmaCrossScript`, `EmaRibbonScript`, `MacdFullScript`, `Rsi14Script`), matching `_registered_class_names()`'s same 9; `_DOMAIN_DIR.rglob("*.py")` now scans 11 real files. Mutation-verified `test_domain_layer_never_imports_a_ui_toolkit` on the fixed tree by temporarily appending `import PySide6` to `rsi_14_script.py` — the test failed naming that exact offender — then restored the file (`git diff --stat` empty afterward).

## Verification

- `.venv/bin/ruff check tests/unit/support/indicators/test_indicator_script_conventions.py tests/unit/architecture/scanned_roots_registry.py` — passed.
- `.venv/bin/ruff format --check` on the same two files — passed.
- `PYTHONPATH=.. QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/unit/architecture -q` — 419 passed (includes `test_scanned_roots_are_not_empty.py`'s full parametrized suite against the corrected registry row).
- `PYTHONPATH=.. QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/unit/support/indicators -q` — 257 passed.
- Fast tier only (`ci-rule.md` §1 "Every Commit"); this is a doc/test-only architectural-guard fix touching no `src/` runtime code, so the full `ci-local.ps1 -Full` gate is left to the PR's own CI run per the two-tier cadence.

## Suggested next steps

None — closed. A separate follow-up (`test_scanned_roots_are_not_empty.py` cannot detect a guard whose source diverges from its own correctly-registered root) was queued as a standalone task suggestion rather than folded into this bug's fix.
