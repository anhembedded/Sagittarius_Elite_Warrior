# BUG-030 — Full parallel test run (`-n 6`) dies mid-suite after `ResourceWarning: unclosed database`, no summary

**Reported:** 2026-08-21 — found running the real `.\scripts\ci-local.ps1
-Full` gate (previously this session only ran sequential `pytest` on
`tests/unit/`, which never exercises this).
**Severity:** 🟡 P2 — does not affect the shipped app (test-infrastructure
only), but silently breaks the mandatory local CI gate's "Tests" step under
its own default parallel settings, with no useful summary to diagnose from.
**Status:** 🔴 **Open — reproduced twice at the identical spot, root cause
narrowed to a resource-leak class but not pinned to one exact source.**

## Symptom

`.\scripts\ci-local.ps1 -Full` (6 xdist workers, `Sagittarius_Elite_Warrior/tests`
minus `sanity`/flaky-UI) — the "Tests" step fails with **no pytest summary
line at all** (no "`X passed, Y failed`"), `$LASTEXITCODE` non-zero. The
captured log's last lines before the script moves on to "Waiting for sanity
job to complete..." are:

```
Sagittarius_Elite_Warrior\tests\unit\application\services\test_strategy_factory.py::test_build_engine_wires_a_fresh_strategy_with_its_own_indicators
C:\Users\hoang\...\.venv\Lib\site-packages\_pytest\unraisableexception.py:33: ResourceWarning: unclosed database in <sqlite3.Connection object at 0x...>
```

No `PASSED`/`FAILED` line ever prints for that test — worker `gw0` simply
stops producing output. **Reproduced twice, independently, landing at the
exact same test on the exact same worker both times** (different SQLite
`Connection` object addresses each run, confirming genuinely separate runs,
not a duplicated log) — this is not flaky/random; it is a real, deterministic
condition given the same test collection and 6-worker split.

## What is confirmed, to narrow the search

- **Not caused by the test where it appears.** `test_strategy_factory.py::test_build_engine_wires_a_fresh_strategy_with_its_own_indicators`
  is pure domain code — `StrategyRegistry`, `Mock()`, no I/O, no SQLite
  anywhere in it or its imports. `pytest`'s `unraisableexception` plugin
  attaches an unraisable exception/warning (fired during GC finalization,
  which has no normal call stack to raise into) to whatever test happens to
  be running on that worker at the moment the finalizer runs — so this test
  is an innocent bystander, not the leak source.
- **Not caused by `test_shutdown_database_sync_process.py`** (runs
  immediately before, on the same worker, and is the most obvious suspect —
  real subprocess + real SQLite files). Read the file: it only does
  `subprocess.run([sys.executable, "-m", "...shutdown_database_sync_probe", mode], ...)`.
  Any SQLite connection opened *inside* that child process is reclaimed by
  the OS when the subprocess exits — it cannot leak a Python-level object
  back into the `gw0` worker process.
- **Not caused by `test_sqlalchemy_repository.py`'s standard fixture.**
  Every one of its 15 tests uses the same `repo` fixture, which already
  explicitly calls `db_manager.dispose_all()` in teardown with a comment
  acknowledging this exact class of bug ("Without this Python's GC fires
  ResourceWarning: unclosed database") — this file's own author already
  fixed it for every test that goes through `repo`.
- **Leading suspect, not confirmed:** `test_stream_klines_never_holds_more_than_a_bounded_number_of_rows_live`
  (BUG-025's backtest-side memory regression test, in the same
  `test_sqlalchemy_repository.py`) calls `gc.collect()` **repeatedly and
  explicitly** to sample live object counts. An explicit `gc.collect()`
  force-finalizes *every* currently-unreachable object process-wide, not
  just this test's own — so it is a very plausible place for a **pre-existing,
  unrelated leak from some earlier test/fixture** (anywhere in `gw0`'s test
  history, not necessarily in this file) to finally get collected and warned
  about, at a point that reads as "random" relative to the real leak's true
  origin. This is a hypothesis with strong circumstantial support (the
  `gc.collect()` calls are a uniquely aggressive pattern in this test suite,
  new from the same BUG-025 backtest-streaming work), not yet proven by
  bisection.

## Suggested next steps (not yet attempted)

1. **Bisect by disabling tests, not by reading code further.** Run the same
   `Sagittarius_Elite_Warrior/tests` scope with `-n 6` repeatedly, each time
   deselecting (`--deselect`) a candidate block (start with everything in
   `tests/integration/infrastructure/persistence/` and `tests/integration/presentation/`),
   until the crash stops reproducing — narrows to the actual leaking
   fixture/test, not just a plausible one.
2. **Add a session-scoped autouse fixture** that runs `gc.collect()` +
   `warnings.catch_warnings(record=True)` after every test and reports which
   test's teardown first makes an unclosed-`sqlite3.Connection` object
   collectible — turns "some earlier test leaked it" into a specific file:line.
3. Once the real source is found, apply the same fix pattern already proven
   in this file's own `repo` fixture (`dispose_all()` in teardown) or in
   `BUG-023`'s completed report (which fixed the equivalent production-code
   class of this bug — `DatabaseManager`/`SqliteMarketDataRepository` engines
   not being disposed on shutdown).
4. Confirm the fix by re-running `ci-local.ps1 -Full` at least 3 times in a
   row with no `-SkipNativeBuild`/`-UnitOnly` shortcuts — this bug only
   manifests under the real full parallel scope, never under
   `pytest tests/unit/ -n 6` alone (verified: that narrower command passed
   cleanly, 1678/1678, in the same investigation that found this bug).

## Note

Found only because the user pushed to actually run the real `-Full` gate
(with a real captured log) instead of trusting a narrower, faster command as
a stand-in — `tests/unit/ -n 6` alone is clean and would never have surfaced
this; it needs the broader `unit + integration` scope's real SQLite/subprocess
tests present to trigger.
