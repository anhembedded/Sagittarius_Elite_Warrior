# BUG-121 — the UI integration tier hangs or aborts when its 47 tests run in one process

- **Reported:** 2026-09-15
- **Severity:** ⚪ **Closed — not reproducible from the current environment** (was 🟠 P2)
- **Status:** ⚪ **Closed 2026-09-19 (user decision).** Investigated 2026-09-19: 15/15
  reproduction attempts clean (10 sequential, 3 xdist+randomized, 2 full-gate CI runs on
  the hardened tree), root cause **not** confirmed. See §7 for what closing this record
  means and does not mean.

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
   `fix-bug-rule.md` §3 asks for.
3. Fix `pytest-timeout`'s blind spot for this tier: `--timeout-method=thread` kills the
   process from a watchdog thread and does not depend on the main thread returning to
   Python. That is a one-line change in `pyproject.toml` and it converts every future hang
   here into a readable failure, which is worth doing **before** the root cause is found.
4. Only then decide whether `BUG-056`'s drain needs to move (e.g. into `main_window`'s
   teardown before widgets are destroyed, rather than `app_engine`'s after).

## 5. Why it is filed rather than fixed

It surfaced while verifying `EPIC-025` PR 1.1a's review cleanup, and it predates that
cleanup: the merged tree hangs too. Fixing it means root-causing cross-test state leakage in
a 47-test Qt tier, which is its own task and not a review follow-up — and `fix-bug-rule.md`
§1 forbids the shortcut of fixing the symptom (a longer timeout, a re-run) that is the only
thing that fits inside this one.

## 6. 2026-09-19 — steps 2 and 3 applied; step 1 not yet reproducing

Picked back up per user request to use `fix-bug-rule.md`/`fix-bug` skill going forward.
User approved the `pyproject.toml` change (§4 item 3) explicitly, since `commit-rule.md`
requires prior confirmation for any `pyproject.toml` edit.

**Applied (both committed together, verified green):**
- `pyproject.toml`: `timeout_method = "thread"` — pytest-timeout's watchdog now runs on its
  own OS thread and can kill the process regardless of what the main thread is blocked in,
  closing the exact gap this report's §2 names (`SIGALRM`, the `signal`-method default,
  cannot be delivered while the main thread sits in Qt's C++ event loop or
  `Executor.shutdown(wait=True)`).
- `tests/integration/presentation/ui/conftest.py`: both `thread_manager.shutdown(wait=True)`
  call sites (`app_engine` and `main_window` teardown) now assert
  `thread_manager.stats().in_flight == 0` immediately after the drain returns — direct,
  positive proof the drain actually covered every submitted task for that test, using the
  engine's own `PoolStats` rather than name-sniffing live threads (asyncio's default executor
  and other libraries also spawn `ThreadPoolExecutor`s with the same default naming, which
  would have made a thread-enumeration check unreliable).

**Step 1 (bisection) — not reproducing yet.** Ten consecutive sequential runs of the full
directory (`pytest tests/integration/presentation/ui -q -p no:randomly`, single process, no
xdist — the same shape as this report's original measurement), 2026-09-19, on
`d9ceb768` + these two changes: **10/10 clean** — 43 passed, 4 skipped, ~85s each, every
time. Neither new assertion fired; no hang, no abort. This report's original measurement
(2026-09-15) saw the hang on roughly half of five runs on an earlier commit
(`78e44971`) — worth naming honestly rather than guessing: either the race window
narrowed or closed as a side effect of unrelated work since then (`EPIC-025` Phases 4-5's
restructuring, or `BUG-014`'s fix, which added `app.stop()` teardown to 24 test files and
could plausibly have quieted a related shutdown race), or it needs a condition these ten
runs did not hit (xdist parallelism, `pytest-randomly`'s reordering, `dev_mode=True`).

**2026-09-19, later the same day — the `timeout_method` fix rescoped per independent review.**
This report's `pyproject.toml` change above originally set `timeout_method = "thread"`
globally. An independent reviewer on `BUG-131`'s PR #246 (which this commit rode on, see
that PR's thread) correctly found that takes `signal`-method's per-test traceback isolation
away from the other ~5000 tests in the suite for a hang that only reproduces in this one
47-test tier. Rescoped: `pyproject.toml` reverted to the platform-default `signal` method
globally; `tests/integration/presentation/ui/conftest.py` gained a
`pytest_collection_modifyitems` hook that marks every test it collects
`@pytest.mark.timeout(60, method="thread")`, so only this tier trades isolation for a
watchdog that actually fires. Verified the marker is scoped correctly, not just present:
`pytest ... -m timeout --collect-only` on a file in this directory collects all 7 of its
tests; the same query against `tests/unit/architecture/` collects 0. Full tier re-run after
the rescope: 43 passed, 4 skipped, no regression; `tests/unit/architecture -q`: 419 passed.

**2026-09-19, reproduction attempts under the gate's actual shape.** Three more runs,
`pytest tests/integration/presentation/ui -q -n 4` (xdist, default worker count on this
4-core box — matches `ci-local.ps1`'s `min(nproc, 6)`; `pytest-randomly` left enabled,
unlike the earlier sequential runs): **3/3 clean**, 43 passed / 4 skipped, ~28s each. Plus
two full-gate GitHub Actions runs on this same branch (`39ce8ad2`, `ddedd341`), both of
which exercise this tier under xdist+randomly as part of the 5052-test unit+integration
run: both green, log-scanned, no hang.

**Running total: 15/15 clean** across sequential (10) and parallel/randomized (5) shapes,
on the current tree with both hardening changes in place. No reproduction since picking
this back up. Recommendation and disposition options handed to the user rather than
decided here — see chat.

**Status:** left Open. The diagnostic improvements are real, standalone value on their own
(a future hang in this tier now fails loudly and names itself instead of silently eating the
CI timeout budget) and are not being held back by non-reproduction — but they are not a fix
for the reported leak, since no leak has been reproduced to fix. Not closing this on ten
clean runs of a bug that was already known to be intermittent; the honest state is
"substantially hardened, still not reproduced, root cause still not established."

## 7. Closed 2026-09-19 — user decision to stop investigating without a live reproduction

**Closed because it stopped reproducing, not because a mechanism was found and fixed.** No
line of production code changed for this defect. §6 already lists 15/15 clean attempts
across every shape this report's own evidence pointed at (sequential single-process, xdist,
`pytest-randomly` enabled, and two green full-gate CI runs on the hardened tree) — asked
whether to keep chasing it further (more repetitions, `dev_mode=True`) or stop, the user
chose to close.

### 7.1 What stays, regardless of closure

The two 2026-09-19 hardening changes are permanent, independent of this record's status:
- `tests/integration/presentation/ui/conftest.py` asserts `thread_manager.stats().in_flight
  == 0` right after both `shutdown(wait=True)` drains — if the leak this report describes
  (or one shaped like it) ever recurs, it now fails naming the exact count in flight instead
  of silently surviving into the next test.
- The same file's `pytest_collection_modifyitems` hook marks every test in this tier
  `@pytest.mark.timeout(60, method="thread")` — a hang here now kills the run within 60s
  with a full thread dump, instead of running past `signal`-method's blind spot (the main
  thread stuck in Qt's C++ event loop never returns to run the handler) until the CI
  runner's own outer kill, naming nothing.

So this closure is not a return to the original silent-hang state `BUG-119` and this report
both describe — a live recurrence of the underlying leak would now be caught, just under a
different (new) bug number rather than this one staying open on zero live evidence.

### 7.2 Why this is a defensible "closed", not a guess dressed up as one

Fifteen attempts is not exhaustive, but it spans every axis this report's own evidence
named as possibly relevant: process topology (1 process vs. 4 xdist workers), test order
(fixed vs. `pytest-randomly`), and the actual CI harness (two real GitHub Actions runs, not
just a local approximation). None reproduced. The honest remaining hypotheses (§6): the race
window narrowed or closed as a side effect of unrelated work since 2026-09-15 (`EPIC-025`
Phases 4-5, or `BUG-014`'s `app.stop()` teardown fix), or it needs a condition none of the
fifteen runs hit (`dev_mode=True` is the one named in §6 that was not tried).

### 7.3 If it comes back

Open a **new** bug report, reference this one and `BUG-119`, and start from whichever of the
15 runs' conditions is now producing the hang (the `dev_mode=True` gap in particular).
Re-read §1-§3's evidence here first — the worker-thread and widget-survival stack traces are
still the two most concrete leads this investigation ever had, and nothing in this closure
invalidates them.
