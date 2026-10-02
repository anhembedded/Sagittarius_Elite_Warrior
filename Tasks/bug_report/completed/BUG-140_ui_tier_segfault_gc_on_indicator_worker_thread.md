# BUG-140 — The UI integration tier sometimes dies with a segfault while the Dev Board loads indicator history

- **Reported:** 2026-09-29 (seen by the author session during `EPIC-028B` verification; filed at the `PR #294` independent review's request, finding 3)
- **Severity:** 🟡 P2 — the test process dies (exit 139) and takes the whole `tests/integration/presentation` tier with it; the same mechanism once hung that tier. Whether it reaches users of the running app is not yet established.
- **Status:** ✅ Fixed 2026-10-02 (`PR #311`)
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

## Second occurrence (2026-10-02, `PR #311`, GitHub Actions)
`ci-local.ps1 -Full`, unit tier, xdist worker. The crashing thread was **xdist's execnet receiver thread**, not an app worker:
```
Current thread (most recent call first):
  Garbage-collecting
  File ".../threading.py", line 623 in set
  File ".../xdist/remote.py", line 107 in lock
  File ".../xdist/remote.py", line 93 in put
```
The main thread was in `src/support/ui_kit/table_model.py:133 columnCount` ← `open_orders_panel.py:174 selected_row` ← `test_open_orders_panel.py:58 _select_row`. The worker's earlier tests were `test_holdings_panel.py` and `test_open_orders_panel.py`. The diff under test (`pyproject.toml` only) could not cause it.

## Root cause
CPython runs a generational collection on **whichever thread allocates past the threshold** (`gc.get_threshold()`, 700 for the youngest generation). A Qt view, panel or dialog is a reference cycle (the view holds its view-model or model, the signals hold the view's bound slots), so only the cyclic collector frees it, and it finalizes the Qt wrappers on the thread that runs the collection. When that thread is not the main one, a widget tree is torn down while the main thread is inside Qt on related objects: native memory corruption, `Segmentation fault`, or the earlier `connectImpl`/`disconnect` deadlock.

Both occurrences are this one mechanism, and only the allocating thread differs: a `concurrent.futures` worker feeding indicators (`runner.py:268`), and execnet's receiver thread handling a command. Nothing in the app or the suite controlled where collection ran. `BUG-065` met the same hazard single-threaded and fixed it per call site (`qtbot.addWidget()` for one dialog), which left every other cycle to the collector's schedule and thread.

Proven, not inferred: a cycle with a `__del__` that records its thread, then 200,000 container allocations on a worker thread, was finalized on the worker thread twice out of two (`tests/unit/test_garbage_is_collected_on_the_main_thread.py`, red before the fix).

## Fix
Automatic collection is off for the whole process, and the main thread collects on CPython's own schedule (pyqtgraph's `GarbageCollector` pattern, for the same reason):
- `src/support/ui_kit/main_thread_collection.py`: `stop_automatic_collection()`, and `collect_due_generations()`, which collects each generation whose count passed its threshold and raises `RuntimeError` off the main thread. No Qt import.
- `src/support/ui_kit/main_thread_garbage_collector.py`: `MainThreadGarbageCollector`, a 100 ms `QTimer` owned by the `QApplication`. `app_bootstrapper.build()` starts it right after the `QApplication` exists and logs `[gc-policy]` at INFO. It has no `stop()`: turning collection back on while a worker lives is the hazard.
- `tests/conftest.py`:
  - `pytest_configure` stops automatic collection in every test process, so it is already off when collection-time imports run.
  - The autouse fixture `_collect_garbage_on_the_main_thread` re-applies the policy before each test and collects what is due after it, before `_flush_qt_deferred_deletes` delivers the deletions.
  - The `qapp` fixture starts the same timer.
- `test_qt_object_release.py`'s `_no_automatic_gc` fixture restores the previous state instead of turning collection on.

## Regression test
- `tests/unit/test_garbage_is_collected_on_the_main_thread.py`:
  - a worker-thread allocation burst finalizes nothing;
  - the main thread's `collect_due_generations()` finalizes the cycle;
  - a call off the main thread is refused;
  - the fixture is autouse and automatic collection is off.

  With the `conftest.py` wiring removed, three of the four fail on the assertion, not on an import.
- `tests/unit/support/ui_kit/test_main_thread_garbage_collector.py`: the timer collects a cycle on the main thread. With `self._timer.start()` removed, `waitUntil` times out.
- `tests/sanity/test_self_check_process.py`: the real `--self-check` process logs `[gc-policy] automatic collection off`, so removing the line from `build()` fails the sanity tier.

## Verification
- **Positive proof in the real process:** `python -m ...app_bootstrapper --self-check` printed `App.UiKit.GarbageCollector - INFO - [gc-policy] automatic collection off; the main thread collects due generations every 100 ms (BUG-140)` right after `App booted successfully`, and exited 0.
- **Checks:** `ci-local.ps1 -SkipTests` passed, and its log has no `FAILED|ERROR|Traceback|ResourceWarning`. The unit and integration tiers were run under xdist; the results are in `PR #311`.
- **Not provable locally:** the crash is intermittent (1 run in 4 at worst), so its absence in a few runs is not proof. The proof is the mechanism: no thread but the main one can now run a collection. GitHub Actions' full gate on the PR is the authority.
- **Case study:** not written. The defect never reached a user (criterion 1 of `Docs/CASE_STUDIES/README.md`).
