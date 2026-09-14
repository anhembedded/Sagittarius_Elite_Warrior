# BUG-119 — the full gate stalls deterministically after exactly 3993 tests

- **Reported:** 2026-09-14 (found while fixing `BUG-118`, during `EPIC-025` PR 0.4a-2)
- **Severity:** 🔴 P1 — `scripts/ci-local.ps1 -Full` cannot be run to completion, and it is the
  mandatory gate for every commit, merge and "done" claim (`.agents/rules/ci-rule.md` §1). Nothing
  can be verified while this holds.
- **Status:** Open — reproduced reliably, **root cause not found**. Read §6 before starting.

> **This report is written to be picked up cold.** It assumes no knowledge of the session that
> found it. Everything needed to reproduce and continue is below, including what has already been
> ruled out, so no one repeats that work.

---

## 1. Symptom

The gate runs, then stops making progress. It never fails and never finishes:

```
pwsh -NoProfile -File scripts/ci-local.ps1 -Full
  ✅  Ruff Lint passed
  ✅  Ruff Format passed
  ✅  Mypy passed
  ✅  Skill Prompt References passed
  ▶  Full Tests (4 workers, excl. sanity) + Sanity (1 core) — running concurrently
  ...
  [ 96%]        <- stops here, forever
```

No test reports `FAILED`. No traceback. No `INTERNALERROR`. No worker-crash notice. The process
tree stays alive and idle indefinitely; it has been left for 6+ minutes with no further output.

## 2. The key fact: it is deterministic, not a resource flake

Three separate runs were compared. They are not merely similar — they are identical:

| Run | Tests reported PASSED | Progress reached | Log size (bytes) |
| :--- | :-: | :-: | :-: |
| gate5 | **3993** | 96% | 1262900 |
| gate6 | **3993** | 96% | 1262900 |
| gate7 | **3993** | 96% | 1262940 |

Set-differencing the test IDs that appear in each log:

```
gate5 vs gate6 — differing test ids: 0
gate5 vs gate7 — differing test ids: 0
```

**The same 3993 tests run, and the same tests never run, every time.** Two of the logs are
byte-identical in size. This rules out memory pressure, machine contention and ordinary flakiness
as the cause — all of those vary between runs.

The last test *named* on the console is **not** the culprit and changes between runs (it is simply
whichever test was in flight when the worker went idle). Do not chase it:

| Run | Last test named | Verified |
| :-- | :--- | :--- |
| gate5, gate6 | `tests/unit/application/use_cases/trading/test_arm_strategy.py::test_an_unknown_strategy_key_is_named_not_crashed_on` | 9 passed in 1.97 s on its own; 3 statements, no threads, no Qt, no I/O |
| gate7 | `tests/unit/shell/test_config_writer.py::test_set_then_save_reaches_the_file` | passes on its own |

### Which tests never get scheduled

161 under `tests/unit/presentation/`, 10 under `tests/unit/modules/`, ~170 in total. By file, the
largest groups:

```
 19  tests/unit/presentation/ui/common/test_app_defaults.py
 13  tests/unit/presentation/cli/test_interactive_shell.py
 12  tests/unit/presentation/ui/common/test_strategy_arming_coordinator.py
  8  tests/unit/presentation/ui/common/test_live_order_book_coordinator.py
  8  tests/unit/modules/market_data/contracts/test_symbol_market_metadata.py
  7  tests/unit/presentation/ui/common/test_health_feed.py
  6  tests/unit/presentation/ui/common/test_action_ownership_tracker.py
  6  tests/unit/presentation/test_enum_labels.py
```

(Derived by diffing the test IDs in a passing run's log against a stalled run's log. Some entries
in a raw diff are files that PR 0.4a *moved*, which is expected noise — the list above is after
accounting for that.)

## 3. Where the processes actually are

This is the evidence that matters, and it was obtained with `py-spy` (installed into `.venv`
during the investigation; the gate's own console output cannot answer this).

**The xdist controller** — waiting for an event from any worker:

```
$ .venv/bin/py-spy dump --pid <controller>
Thread (idle): "MainThread"
    wait (threading.py:359)
    get (queue.py:180)
    loop_once (xdist/dsession.py:154)
    pytest_runtestloop (xdist/dsession.py:138)
    ...
Thread (idle)  x4
    read (execnet/gateway_base.py:534)
    _thread_receiver (execnet/gateway_base.py:1160)
```

**Every one of the four workers** — idle, waiting to be given work:

```
$ .venv/bin/py-spy dump --pid <each worker>
Thread (idle): "MainThread"
    wait (threading.py:355)
    integrate_as_primary_thread (execnet/gateway_base.py:385)
    serve (execnet/gateway_base.py:1273)
    serve (execnet/gateway_base.py:1806)
Thread (idle)
    read (execnet/gateway_base.py:534)
    _thread_receiver (execnet/gateway_base.py:1160)
```

So: **the controller believes work is outstanding and waits for a report; all four workers believe
they have nothing to do and wait for work.** Nobody is running a test. Nobody is blocked on a lock
inside application code. ~170 tests are never dispatched.

A note on reading `ps`: its `%CPU` column is an average over the process's whole lifetime, not an
instantaneous figure. During this stall it shows workers at 40-95%, which looks like work in
progress and is misleading — the py-spy dumps above are what established they are idle.

## 4. What has been ruled out, with evidence

Do not re-test these.

| Hypothesis | Verdict | Evidence |
| :--- | :--- | :--- |
| A specific test hangs | ❌ | The named test differs between runs and passes alone in ~2 s |
| Out of memory / OOM killer | ❌ | `oom_kill 0` in `/proc/vmstat`; nothing was killed |
| Disk or inode exhaustion | ❌ | 28 GB and 16.5 M inodes free at the time of the stall |
| A worker crashed or was replaced | ❌ | No "node down" / "replacing" / `INTERNALERROR` / `Fatal Python error` / `Segmentation fault` anywhere in the logs; all four workers alive in the dumps |
| Machine contention from other work | ❌ | The stall reproduces byte-identically; contention would vary. A later run on a fully idle box (load 0.03, 15.2 GB free) behaved the same |
| Deadlock in application threads | ❌ | No worker is inside application code at all — all are in `execnet.serve()` |
| The `BUG-118` memory leak | ❌ | Fixing it cut worker peak RSS from 3.4 GB to well under 1 GB. The stall still happened, at the same 3993 |

`BUG-118` (UI tests leaking Qt objects until workers reached 3.4 GB) was found and fixed during
this same investigation, and for a while looked like the explanation. It is a real, separate bug —
and it is **not** this one. Both were originally thought to be one problem; the determinism
evidence in §2 separated them.

## 5. Reproduction

```bash
cd /home/user/Sagittarius_Elite_Warrior
pwsh -NoProfile -File scripts/ci-local.ps1 -Full > /tmp/gate.log 2>&1
# watch: grep -oE '\[ *[0-9]+%\]' /tmp/gate.log | tail -1
# it reaches 96% and stops; the process stays alive
```

The gate's own pytest invocation, for reproducing without the PowerShell wrapper (run from
`/home/user`, the package's parent):

```bash
PYTHONPATH=/home/user QT_QPA_PLATFORM=offscreen \
  Sagittarius_Elite_Warrior/.venv/bin/pytest Sagittarius_Elite_Warrior/tests -v \
  --rootdir=/home/user/Sagittarius_Elite_Warrior \
  --ignore=Sagittarius_Elite_Warrior/tests/sanity \
  --ignore=Sagittarius_Elite_Warrior/tests/testnet \
  --cov=Sagittarius_Elite_Warrior/src --cov-report=term-missing --cov-fail-under=80 \
  -n 4
```

Note the gate runs this **concurrently with a separate sanity job** (`scripts/ci-local.ps1`
around line 400), which may or may not matter — see §6.

### Environment

| | |
| :--- | :--- |
| Python | 3.12.3 |
| pytest / pytest-xdist / execnet | 9.1.1 / 3.8.0 / 2.1.2 |
| pytest-cov / coverage | 7.1.0 / 7.16.0 |
| pytest-qt / PySide6 | 4.5.0 / 6.11.1 |
| pluggy | 1.6.0 |
| CPUs / RAM / swap | 4 / 16 GB / **none** |
| Qt platform | `offscreen` |

`pytest 9.1.1` with `pytest-xdist 3.8.0` is worth noting: pytest 9 is recent, and an
xdist/pytest-9 incompatibility in reporting or scheduling would look exactly like this. Nobody has
checked whether this combination is supported.

## 6. Suggested next steps

Ordered by how much they narrow the search per unit of time. Each is one run of ~3-7 minutes.

1. **Coverage on/off.** Re-run the §5 pytest command with the three `--cov*` flags removed. If it
   completes, the interaction is `pytest-cov` + xdist and the search narrows enormously. *(This was
   started but not finished before the session ended — no result to report, so treat it as unrun.)*
2. **Worker count.** Try `-n 2` and `-n 1`. If `-n 1` completes, it is scheduling, not a test. If
   `-n 2` also stalls at a *different* fixed count, that confirms a scheduler boundary rather than
   anything test-specific.
3. **Distribution mode.** Try `--dist loadfile` and `--dist loadscope`. These change how tests are
   grouped onto workers; if one mode completes, the grouping is implicated.
4. **Isolate the never-scheduled set.** Run *only* the ~170 tests from §2 (they are dominated by
   `tests/unit/presentation/ui/common/`). If they pass in isolation, the problem is not in them —
   which is the likely outcome and would point firmly at the scheduler.
5. **Bisect the suite.** If 1-4 are inconclusive, halve `tests/` and find the smallest set that
   still stalls at a fixed count. A deterministic bug bisects cleanly; this is slow but certain.
6. **`--timeout`.** `pytest-timeout` is **not** currently installed. Adding it would convert this
   silent stall into a loud failure with a traceback, which is worth having regardless of the root
   cause — a gate that hangs is strictly worse than one that fails.

**Do not** "fix" this by reducing the worker count in `scripts/ci-local.ps1` until the cause is
known. That would hide a deterministic defect behind a configuration change and leave the gate
quietly dependent on machine shape — and per `.agents/rules/bug-fix-rule.md` §2, patching the one
call site while the mechanism stays broken is a hotfix, which this repository forbids.

## 7. What this blocks right now

`EPIC-025` PR 0.4a-2 (the CLI seam inversion) and the `BUG-118` fix are both **committed locally
but unverifiable** while the gate cannot finish, because `commit-rule.md` §1 requires a green gate
before a commit and `ci-rule.md` §1 requires it before any "done" claim. PR 0.4a is unaffected — it
was merged on the last run that finished (gate3: 4163 passed, 4 skipped, coverage 94.85%).

That gate3 run is also the proof that the suite itself is green: **the 3993 tests that do run all
pass, and the full 4163 passed as recently as the same day.** Whatever this is, it is not a broken
test.
