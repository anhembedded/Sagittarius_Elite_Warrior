# BUG-253 — The sanity shutdown test fails on a pool worker that is one moment from exiting

- **Reported:** 2026-10-21 (the coordinator, from `gate (Rest)` of PR #682 at `be8aa35`)
- **Severity:** 🟢 P3 — a red required check on a run where nothing hung; it costs a re-run and teaches the author to ignore a red Sanity row
- **Status:** ✅ Fixed (2026-10-21)
- **Board:** `test_the_window_shuts_down_within_budget` listed a worker of `IThreadManager`'s pool that was still alive an instant after `shutdown()`; the pool is stopped with `wait=False`, so the check now joins the new non-daemon threads against a 5 s deadline (`tests/sanity/leaked_threads.py`).
- **Context:** Sanity tier (`ci-rule.md` §2) → shell / presentation shutdown (`src/presentation/ui/app_bootstrapper.py`) → `tests/sanity/test_composition_root.py`
- **Environment:** GitHub Actions `ubuntu-24.04`, Python 3.12.15, run 39578136427, head `be8aa35b475fc992ff28935ad11b11af8afdc29d`; the same test passed on the re-run at `0ec9f7a` (run 39579223005).

## Reproduction
Not reproduced on demand: one failure in the CI run above, a pass on the next run of the same test and a pass locally. The mechanism below reproduces it without the application: a `ThreadPoolExecutor` shut down with `wait=False` while a task is still ending, checked at once.

## Symptom
From the `ci-local-logs-Rest` artifact (`logs/ci-local-20261021-093611.log`, line 2121 onward):

```
E       AssertionError: Non-daemon thread(s) still alive after shutdown, which is what keeps the real process from exiting: ['ThreadPoolExecutor-0_2']
tests/sanity/test_composition_root.py:460: AssertionError
FAILED tests/sanity/test_composition_root.py::test_the_window_shuts_down_within_budget
=== 1 failed, 66 passed in 64.42s
```
The shutdown itself was inside its 10 s budget; the log scan of the run was clean.

## Root cause
`test_the_window_shuts_down_within_budget` took `threading.enumerate()` immediately after `window.shutdown()` and failed on any new non-daemon thread (`tests/sanity/test_composition_root.py:455-463` at `be8aa35`). The pool it named is the application's `IThreadManager` pool: the engine shuts it down with `wait=False` on purpose (`src/presentation/ui/app_bootstrapper.py`, `_log_surviving_non_daemon_threads`, docstring), which returns before an idle worker has seen its stop signal and left. So the check sampled a worker that was about to exit, not one that keeps the process alive. The check's own question is the process's: Python's exit joins every pool worker, so only a thread still alive after a bounded wait matters. A sampler with no wait answers a different, racy question; whether it fires depends on scheduling, which is why one run in many failed.

The net that stayed silent: this very test, which had passed on every earlier run and has no wait. No case study (no live defect got through a green gate; the application's shutdown was sound).

## Fix
`tests/sanity/leaked_threads.py` → `non_daemon_threads_left_since`: joins each new non-daemon thread against one shared 5 s deadline (no sleep) and returns the names of those still alive. The test calls it instead of listing the threads at once. A thread that really hangs still fails, after the deadline. The application is unchanged.

## Regression test
`tests/unit/test_the_leaked_thread_check_waits_for_a_worker_that_is_leaving.py::test_a_pool_shut_down_without_waiting_is_not_reported_as_leaked` — red before the fix for this reason: with the join removed (the old instant sample) the worker released after `shutdown(wait=False)` is still alive when listed (failed 3 of 3 runs); green after. Its pair, `test_a_thread_that_never_ends_is_still_reported`, keeps the check from going vacuous.

## Verification
- Both new tests and `tests/sanity/test_composition_root.py` (21) pass locally; the mutation (join removed) turns the first red.
- Positive proof the new mechanism ran: the second test passes only if the join loop reaches the deadline and reports the stuck thread.
- Full gate: the `ci-local.ps1 -Full` check on the pull request's head.
