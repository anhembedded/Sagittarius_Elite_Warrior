# BUG-244 — `test_every_bus_subscriber_is_reachable` timed out at 60 s in CI's `gate (Unit)`

- **Reported:** 2026-10-20 (the author session of PR #651, from the first `gate (Unit)` run on that PR's head; the coordinator asked for the record)
- **Severity:** 🟢 P3 — a green change failed the required `-Full` check once and passed on one re-run; each such failure costs a ten-minute cycle and, if re-runs are unavailable, a blocked merge
- **Status:** Open
- **Board:** The architecture guard `test_every_bus_subscriber_is_reachable` ran past pytest-timeout's 60 s once in CI's `gate (Unit)` (about 9–11 s on a quiet machine); cause not established.
- **Context:** CI and the test gate → `tests/unit/architecture/test_a_bus_subscriber_is_constructed.py` → the guard scans the source for bus subscribers and checks each is constructed by the real graph `create_app()` builds (`CS-002`, `CS-003`)
- **Environment:** GitHub Actions `ubuntu-latest`, Python 3.12.15, `gate (Unit)` with xdist workers (`gw0` ran the test). PR #651 head `5ba859fdabd3309de6d4987738c56d08920a37bc` (attempt 1) and `7afd8cdde3d9a9eb0146a376e88d5eec3b5167f2` (attempt 2). Local container: Linux, Python 3.12.

## Reproduction
Not reproduced. One occurrence in one run; the same test passed on the re-run of the same job and on every other PR run that day.
1. CI runs `gate (Unit)` (`ci-local.ps1 -Full -Part Unit`) over `tests/unit`.
2. `test_every_bus_subscriber_is_reachable` is collected on worker `gw0` at about 30 % of the run.
3. Expected: pass in about ten seconds. Actual: `Failed: Timeout (>60.0s) from pytest-timeout.`

## Symptom
From the job log of GitHub Actions run 39473466066, attempt 1, job 118803265304 (`gate (Unit)`):
```
[gw0] [ 30%] FAILED Sagittarius_Elite_Warrior/tests/unit/architecture/test_a_bus_subscriber_is_constructed.py::test_every_bus_subscriber_is_reachable
FAILED Sagittarius_Elite_Warrior/tests/unit/architecture/test_a_bus_subscriber_is_constructed.py::test_every_bus_subscriber_is_reachable - Failed: Timeout (>60.0s) from pytest-timeout.
  ❌  Tests FAILED
  ✅  Run log — no WARNING/ERROR/CRITICAL log records, nothing uncollectable
```
Every other test passed, and the run-log scan was clean. On the same head the re-run of the job (attempt 2) passed. Measured here, on the same source tree: 11.3 s on the PR's head and 8.7 s on `master-warrior` (`pytest --durations`), so the PR's change (one more subscriber) adds little.

## Root cause
Not yet established. What is known: the test is a source scan plus a real `create_app()` build, so it is the slowest guard in the architecture directory, and a loaded shared runner running several xdist workers can plausibly stretch ten seconds past sixty. What is not known: how long the test takes on a CI runner when it passes (the log keeps no per-test duration), and whether anything in it can block (a lock, a thread, a filesystem wait).

## Fix
Pending.

## Regression test
Not applicable until the cause is known.

## Verification
Not run.

## Suggested next steps
1. Read the `--durations` of the next several `gate (Unit)` jobs for this test (the artifact `ci-local-logs-Unit` holds the run log) and record the spread.
2. If the spread is wide, find what dominates: the source scan or the `create_app()` build, and whether the scan can be cached across the three tests in the file or made cheaper.
3. Raise the timeout for this one test only with a recorded measurement, never by lowering the guard (`CONSTITUTION.md` P8).
