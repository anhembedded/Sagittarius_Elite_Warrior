# BUG-121 — the UI integration tier hangs or aborts when its 47 tests run in one process

- **Reported:** 2026-09-15
- **Severity:** 🟠 P2 — it does not fail the gate, and that is the problem: the gate is the
  only way this tier is ever run, so a developer who runs the directory by hand (which is
  what a person does while writing one of these tests) hits a hang roughly half the time
  and has nothing to read.
- **Status:** Open — reproduced on both trees, root cause **not** established. Filed with
  the evidence rather than a guess, per `bug-fix-rule.md` §7.

## 1. Symptom

Running the tier's own directory in a single process hangs (no output, no timeout ever
fires) or dies with `Fatal Python error: Aborted`:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest \
  --rootdir=<repo> <repo>/tests/integration/presentation/ui -q -p no:randomly
```

Measured 2026-09-15, five runs per tree, 300 s timeout:

| Tree | Result |
| :--- | :--- |
| `78e44971` (master-warrior, `EPIC-025` PR 1.1a merged) | run 1 **PASS** (43 passed, 102 s) · run 2 **HANG** (killed at 300 s) |
| the PR 1.1a review cleanup, unpushed | **ABORT** · **PASS** · **HANG** · **FAIL** (`libshiboken … already deleted`) · **HANG** |

So it is **not** introduced by the cleanup — it reproduces on the merged tree — but the
rate looks worse there, and with this few runs that difference is not yet a measurement.

Two distinct endings, and both point at the same neighbourhood:

**(a) A worker thread that outlived its test.** `SIGABRT` (or `kill -ABRT` on the hung
process) dumps a `ThreadManager` worker still inside the *previous* test's history load
while the main thread is in the *next* test's fixture setup:

```
Thread 0x00007fb3f6ffd6c0 (most recent call first):
  File "src/domain/indicator_scripts/base_indicator_script.py", line 505 in drain_region
  File "src/presentation/ui/components/indicator_scripts/runner.py", line 253 in feed
  File "src/presentation/ui/components/indicator_scripts/runner.py", line 309 in feed_all
  File "src/presentation/ui/screens/dashboard/stream_lifecycle_controller.py", line 439 in _run_load_history
  File "src/presentation/ui/screens/dashboard/stream_lifecycle_controller.py", line 579 in _run_sync_and_start
  ...
Current thread (most recent call first):
  Garbage-collecting
  File ".../pytestqt/wait_signal.py", line 63 in _quit_loop_by_timeout
  ...
  File "tests/integration/presentation/ui/conftest.py", line 543 in _navigate
  File "tests/integration/presentation/ui/test_dev_board_indicators.py", line 161 in
      test_macd_produces_no_series_with_too_little_history
```

This is **the exact shape `BUG-056` already fixed once** — its fix is the
`thread_manager.shutdown(wait=True)` drain in `app_engine`'s teardown, and that comment
block in `conftest.py` describes this abort in detail. Either the drain is not covering the
worker in the dump, or the worker is submitted after it. The hang is plausibly the same
event seen from the other side: teardown blocking in `shutdown(wait=True)` on a worker that
never returns.

**(b) A widget that outlived its test.** One run failed instead of hanging, inside an event
filter, for a test that does not build that widget:

```
FAILED tests/integration/presentation/ui/test_dev_board_known_gaps.py::test_market_dropdown_has_no_presenter_effect
CALL ERROR: Exceptions caught in Qt event loop:
  File "src/presentation/ui/kit/preferred_height_scroll_area.py", line 71, in eventFilter
    return super().eventFilter(watched, event)
RuntimeError: libshiboken: Internal C++ object (PySide6.QtWidgets.QWidget) already deleted.
```

## 2. Why the gate never sees it

`scripts/ci-local.ps1 -Full` runs with `-n min(nproc, 6)`, so xdist splits these 47 tests
across four workers *and* `pytest-randomly` reorders them: no worker runs the sequence that
breaks. Both gate runs on both trees passed (4 397 and 4 401 tests, log scans clean).

`pytest-timeout = 60` (added by `BUG-119`) does not save the hang either: its method is
`signal`, and `SIGALRM` is delivered to the main thread, which is sitting in Qt's C++ event
loop or in `Executor.shutdown(wait=True)` — neither returns to the interpreter to run the
handler. **This is the concrete gap `BUG-119` left**, and it is worth naming on its own:
the repository believes a hang now fails loudly, and for this tier it does not.

## 3. Root cause — not established

What is known: two tests' state (a worker, a widget) survives into a later test, and the
teardown meant to prevent exactly that (`BUG-056`'s drain) is present and evidently not
sufficient for every path. What is *not* known: which test leaks, and whether the leak is a
worker started after teardown began, an `ExclusiveAction` that outlives the presenter, or a
widget whose event filter is never removed. The `_run_sync_and_start` frame says the leaking
test clicked **Start Live**, which narrows it to
`test_dev_board_async_race_conditions.py` — the file whose whole purpose is to widen that
race with an injected delay — but "narrows it to" is not a root cause and this report will
not pretend otherwise.

## 4. Suggested next steps

1. Bisect the leak by file, not by theory: run the directory as `--deselect`ed halves until
   a minimal pair reproduces. The pair
   `test_dev_board_async_race_conditions.py + test_dev_board_indicators.py` alone passed
   twice, so the sequence needs more preceding state than those two.
2. Make the leak fail loudly instead of later: a session-scoped autouse fixture that, after
   each test, asserts the `ThreadManager` has no running worker and that no `QWidget`
   created by the test survives — the same "prove the mechanism ran" move
   `bug-fix-rule.md` §3 asks for.
3. Fix `pytest-timeout`'s blind spot for this tier: `--timeout-method=thread` kills the
   process from a watchdog thread and does not depend on the main thread returning to
   Python. That is a one-line change in `pyproject.toml` and it converts every future hang
   here into a readable failure, which is worth doing **before** the root cause is found.
4. Only then decide whether `BUG-056`'s drain needs to move (e.g. into `main_window`'s
   teardown before widgets are destroyed, rather than `app_engine`'s after).

## 5. Why it is filed rather than fixed

It surfaced while verifying `EPIC-025` PR 1.1a's review cleanup, and it predates that
cleanup: the merged tree hangs too. Fixing it means root-causing cross-test state leakage in
a 47-test Qt tier, which is its own task and not a review follow-up — and `bug-fix-rule.md`
§1 forbids the shortcut of fixing the symptom (a longer timeout, a re-run) that is the only
thing that fits inside this one.
