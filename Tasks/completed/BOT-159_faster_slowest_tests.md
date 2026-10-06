# BOT-159 — The gate's slowest tests run faster, proving the same things

**Status:** ✅ Done (2026-10-06)
**Source:** the user, 2026-10-06, after the CI timing measurement: "Oki lam di ban" (okay, go ahead). Before that, the user had asked for GitHub CI to run integration tests only, "vi hien tai luong test case qua nhieu" (because there are too many test cases now). The measurement showed that the time is concentrated in a few tests and in coverage, not in the number of tests.
**Risk:** 🟢 — no test removed or weakened; each changed test was mutation-checked
**Complexity:** S — two files
**Depends on:** None

---

## 1. Context and problem
The green gate of PR #372 took 381 s on GitHub (4 CPUs); 306 s of it was the single pytest run of unit and integration with coverage. Measured locally with the gate's 4 workers and coverage on, unit is 8,443 tests in 177 s and integration is 295 tests in 57 s.
- The slowest 10% of unit tests take 90% of the unit tier's time.
- `test_scanned_roots_are_not_empty.py` took 12.5% of unit time: 158 cases, each running a fresh `rglob()` and `git ls-files`.
- One integration test, the `BUG-052` lingering-thread probe, sat out a fixed 20 s sleep. That was 22% of the integration tier.

## 2. Acceptance criteria
- [x] The scanned-roots guard reads the git index once per run; it still fails on a root with no tracked file of its pattern.
- [x] The `BUG-052` probe exits as soon as it has named the stuck worker; the test still fails if the worker no longer outlives teardown.
- [x] No test is removed, skipped or weakened.

## 3. Design
- **Scanned roots:** every registered pattern names a file, so `rglob(pattern)` below a root is a name match over the tracked paths below it. The tracked paths are read once (`functools.cache`). A path that the index holds but the disk has lost still does not count.
- **Probe:** the stuck task waits on an `Event` capped at the same 20 s, instead of sleeping. The probe sets the event after teardown, the diagnostic and its own survivor scan have all seen the worker. If the probe never reaches its verdict, the cap still ends the process.

## Implementation notes (written when done)
- `test_scanned_roots_are_not_empty.py`: 21.1 s → 1.9 s, 158 passed. Mutation: a registry row's pattern changed to `*.nothing_here` fails every one of that guard's rows.
- `test_shutdown_lingering_thread_diagnostic.py`: about 28 s → 11.6 s for both tests. Mutation: releasing the task before teardown fails `test_a_task_outliving_shutdown_is_named_rather_than_hanging_silently`.
- **Not done, measured and rejected:** `test_backtest_presenter.py` (about 50 s, 221 tests) builds a real, shown `BackTestView` per test, and half of that time is pyqtgraph painting.
  - A presenter shared across tests would weaken isolation.
  - Not showing the view would make the many `isVisible()` assertions vacuous.
  - `WA_DontShowOnScreen` saved only 2 s (49.8 → 47.5).
- **Side finding:** the green gate's log carries `ResourceWarning: gc: 5 uncollectable objects at shutdown`, filed as `BUG-152`.
