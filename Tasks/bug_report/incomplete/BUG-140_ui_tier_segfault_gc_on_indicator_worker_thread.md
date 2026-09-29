# BUG-140 — The UI integration tier sometimes dies with a segfault while the Dev Board loads indicator history

- **Reported:** 2026-09-29 (seen by the author session during `EPIC-028B` verification; filed at the `PR #294` independent review's request, finding 3)
- **Severity:** 🟡 P2 — the test process dies (exit 139) and takes the whole `tests/integration/presentation` tier with it; the same mechanism once hung that tier. Whether it reaches users of the running app is not yet established.
- **Status:** Open
- **Context:** Dev Board live chart (`SPEC` trading dashboard journey) → `src/modules/trading/ui/dashboard/` → `stream_lifecycle_controller.py` (worker thread) → `src/support/indicators/ui/runner.py` (presentation)
- **Environment:** Linux container, `QT_QPA_PLATFORM=offscreen`, Python 3.12, PySide6 6.11.1, `master-warrior` at `f4fc09a5` + the `EPIC-028B` diff. No credentials involved.

## Reproduction
1. `PYTHONPATH=.. QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/integration/presentation -q`
2. Expected: all tests pass. Actual (1 run in 4 during `EPIC-028B`): `Fatal Python error: Segmentation fault` inside `test_dev_board_indicators.py::test_macd_produces_no_series_with_too_little_history`.

Frequency: intermittent. 1 segfault in 4 full-tier runs on 2026-09-29, and 1 earlier hang with the same stack (captured with `py-spy dump`). The next three runs were green.

## Symptom
The crashing thread is a `concurrent.futures` pool worker, **inside the garbage collector**:
```
Current thread 0x00007f2d0bfff6c0 (most recent call first):
  Garbage-collecting
  File ".../src/support/indicators/ui/runner.py", line 268 in feed
  File ".../src/support/indicators/ui/runner.py", line 329 in feed_all
  File ".../src/modules/trading/ui/dashboard/stream_lifecycle_controller.py", line 438 in _run_load_history
  File ".../src/modules/trading/ui/dashboard/stream_lifecycle_controller.py", line 583 in _run_sync_and_start
```
The main thread was in `tests/integration/presentation/ui/conftest.py:554 _navigate`.

The earlier hang had the same worker stack: the main thread was in `QObject::connectImpl` and the pool thread was in `QObject::disconnect`, called from `runner.py:268`.

## Root cause
Not yet established. Hypothesis, not verified: a collection triggered on the worker thread finalizes a Qt object (a signal connection or a `QObject` wrapper) that the main thread also owns, so Qt objects are torn down off their own thread.

## Fix
Not started.

## Regression test
Not yet written.

## Verification
Not run.

## Suggested next steps
- Reproduce with `-p no:randomly` and repeated runs of `test_dev_board_indicators.py` alone, under `PYTHONFAULTHANDLER=1`.
- Read what `runner.py:268` creates or drops per `feed()`, and whether any `QObject`/`Signal` lives in that path.
- Check whether `_run_load_history` should hand the indicator feed to the main thread (`async-ui-action-rule.md`).
