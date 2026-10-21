# BUG-244 — `test_every_bus_subscriber_is_reachable` timed out at 60 s in CI's `gate (Unit)`

- **Reported:** 2026-10-20 (the author session of PR #651, from the first `gate (Unit)` run on that PR's head; the coordinator asked for the record)
- **Severity:** 🟢 P3 — a green change failed the required `-Full` check once and passed on one re-run; each such failure costs a ten-minute cycle and, if re-runs are unavailable, a blocked merge
- **Status:** Fixed (2026-10-21)
- **Board:** `test_every_bus_subscriber_is_reachable` timed out at 60 s once in CI: its scan re-walked the whole AST of every module once per subscribing class (22,892 walks, 11 s quiet, about 45 s profiled), so a loaded runner crossed the limit; each module is now read once (3 s), pinned by a counted test.
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
Established 2026-10-21 at `9c23663`. The guard does no `create_app()` build (the "Context" line above was wrong about that); it is a source scan, and its cost is in `_orphans` (`tests/unit/architecture/test_a_bus_subscriber_is_constructed.py:155`): for each of the 15 subscribing classes it asked `any(name in _identifiers(tree, ...) for tree in trees)`, and `_identifiers` (line 136) walks a whole module's AST with `ast.walk` every time it is called. A subscriber nobody else names (and a named one found late) makes the `any` read most of the 2,159 modules, so the scan read the tree subscribers times modules over: `cProfile` counted 22,892 calls and 8.86 million `ast.walk` steps, 45.8 s under the profiler and 11.4 s on a quiet machine, against the docstring's "one second". The work is CPU-bound Python, so on a shared runner with several xdist workers it stretches with the load: 11 s becomes more than 60 s with no change in the code. Nothing in it can block (no lock, thread or file wait).

## Fix
`_orphans` reads each module once into a map of the names it mentions, asks that map per subscriber, and re-reads only the defining module, without the class's own body, as before. The tree is walked once per module plus once per subscriber (3.1 s here, mostly the parse). The guard finds exactly what it found (`test_the_guard_can_actually_fail` is unchanged and green). The timeout was not raised and nothing was skipped (`CONSTITUTION.md` P8).

## Regression test
`test_each_module_is_read_once_however_many_subscribers_there_are` (same file): three subscribers nobody names over five modules, `_identifiers` counted. Red before the fix (`15 module reads for 5 modules and 3 subscribers`, `assert 15 <= 8`), green after (8). Counted, not timed, so a slow or fast machine decides nothing.

## Verification
The file's four tests pass; `test_every_bus_subscriber_is_reachable` takes 3.1 s (was 11.4 s) on the same machine. The new test was run against the old `_orphans` and failed for the reason above, then against the fix and passed. Commit tier and the architecture directory: see the pull request.
