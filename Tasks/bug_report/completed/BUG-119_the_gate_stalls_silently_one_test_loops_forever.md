# BUG-119 — the full gate stalls silently: one test enters an infinite loop

- **Reported:** 2026-09-14 (found while fixing `BUG-118`, during `EPIC-025` PR 0.4a-2)
- **Severity:** 🔴 P1 — `scripts/ci-local.ps1 -Full` could not be run to completion, and it is the
  mandatory gate for every commit, merge and "done" claim (`.agents/rules/ci-rule.md` §1).
- **Status:** ✅ Fixed 2026-09-14 — root-caused, reproduced in 45 seconds, fixed at the mechanism,
  regression-tested.

> ### ⚠️ This report was first filed with the wrong root cause. Read §3.
>
> The first version of this file concluded "a deterministic xdist scheduling deadlock" and shipped
> six suggested experiments into xdist internals. **That was wrong**, and it would have sent whoever
> picked it up in entirely the wrong direction. The correction is kept in place rather than quietly
> rewritten, because *how* the wrong conclusion was reached is the most reusable thing here.

---

## 1. Symptom

The gate ran, then stopped making progress. It never failed and never finished:

```
pwsh -NoProfile -File scripts/ci-local.ps1 -Full
  ✅  Ruff Lint passed      ✅  Ruff Format passed
  ✅  Mypy passed           ✅  Skill Prompt References passed
  ▶  Full Tests (4 workers, excl. sanity) + Sanity (1 core) — running concurrently
  ...
  [ 96%]        <- stopped here, indefinitely
```

No test reported `FAILED`. No traceback. No `INTERNALERROR`. No worker-crash notice. The process
tree stayed alive; it was left for 6+ minutes with no further output.

Three runs were compared and were **identical**: each stopped after exactly **3993** tests reported
PASSED, two of the logs were byte-identical in size (1262900), and set-differencing their test IDs
gave **zero** difference. The same ~170 tests were never reached every time.

## 2. Root cause

**One test entered an infinite loop, so its worker never reported, so the controller waited
forever.**

`src/modules/market_data/cli/stream_cmd.py::execute_stream()` is a foreground CLI command: after a
successful start it blocks until Ctrl+C.

```python
    if not response.success:
        print(f"Failed to start stream: {response.message}")
        sys.exit(1)
    ...
    while True:
        time.sleep(1)          # by design — a blocking foreground CLI
```

`tests/unit/modules/market_data/cli/test_stream_cmd.py` never covered that loop, and said so in its
own docstring: *"Does not cover the post-start `while True: sleep` loop."* It avoided it by making
dispatch **raise**, so the function exited before reaching it:

```python
    app = Mock(spec=App)
    app.dispatch.side_effect = ConnectionError("Network error")   # the guard
```

`EPIC-025` PR 0.4a-2 then changed `execute_stream()` to dispatch through this application's own
`ICommandDispatcher` port instead of the Engine's `App.dispatch` — so **the code stopped calling
the method the test was mocking**. Three consequences, in order:

1. `app.container.resolve(ICommandDispatcher)` on a `Mock(spec=App)` returns a fresh *permissive*
   `Mock`, not an error;
2. that mock's `.dispatch(...)` returns a `Mock`, so nothing raises and `response.success` is a
   **truthy Mock** — the `sys.exit(1)` guard is passed, not tripped;
3. execution reaches `while True: time.sleep(1)` and the test hangs forever.

Nine sibling tests in the same four files mocked `app.dispatch` too. Those nine merely **failed** —
visible, ordinary, fixable. The tenth *hung*, and a hang is invisible: pytest has no timeout
configured, so the worker simply stopped reporting, the xdist controller kept waiting for it, and
the other workers drained their queues and went idle. Hence a stall at a fixed test count with
nothing red.

Reproduced in 45 seconds once suspected:

```
$ timeout 45 pytest tests/unit/modules/market_data/cli/test_stream_cmd.py -q
Terminated                      <- killed by timeout: the infinite loop
```

## 3. Why the first diagnosis was wrong, and the two mistakes behind it

Worth more than the fix itself, because both mistakes are easy to repeat.

**Mistake 1 — `py-spy` was run on 2 of 4 workers, and the conclusion was stated as if all 4.**
Four workers were running. Two had high resident memory (1.8 GB, 1.7 GB), so those two and the
controller were dumped; they showed workers idle in `execnet.serve()` and the controller waiting on
its queue (`xdist/dsession.py:154`). From that came "all four workers are idle, therefore the
scheduler is deadlocked". The hanging worker was **one of the two never dumped**. The evidence was
partial and the conclusion was not hedged to match. *Dump every worker, or say which ones you
dumped.*

**Mistake 2 — determinism was read as "not my change".** The perfect repeatability (same 3993, same
test IDs, byte-identical logs) correctly ruled out memory pressure and machine contention. It was
then taken as pointing *away* from the in-flight edit — when a hanging test is one of the most
deterministic failures there is. Determinism narrows the search; it never exonerates.

The timeline was available the whole time and said it plainly: the run before the
`ICommandDispatcher` change had **Tests ✅ Sanity ✅** (it failed on Mypy only). Every run after it
stalled. *When a stall starts, diff against the last run that did not stall.*

`BUG-118` (UI tests leaking Qt objects until workers reached 3.4 GB) was found during the same
investigation and is a **real, separate bug**, now fixed. It was briefly believed to be this one.
It is not: fixing it cut worker peak RSS from 3.4 GB to under 1 GB and the stall still landed on the
same 3993.

### Ruled out, with evidence — do not re-test

| Hypothesis | Verdict | Evidence |
| :--- | :--- | :--- |
| Out of memory / OOM killer | ❌ | `oom_kill 0` in `/proc/vmstat`; nothing was killed |
| Disk or inode exhaustion | ❌ | 28 GB and 16.5 M inodes free during the stall |
| A worker crashed or was replaced | ❌ | No "node down" / `Fatal Python error` / `Segmentation fault` in any log |
| Machine contention | ❌ | Reproduced byte-identically, including on an idle box (load 0.03, 15.2 GB free) |
| `pytest-cov` + xdist interaction | ❌ | Re-running the same set with the three `--cov*` flags removed stalled the same way |
| An xdist / pytest 9 scheduling deadlock | ❌ | The controller was waiting correctly — for a worker that was inside `time.sleep(1)` |
| The `BUG-118` Qt memory leak | ❌ | Fixed; stall unchanged, same 3993 |
| The test the console named | ❌ | It differed between runs and passed alone in ~2 s — it was merely in flight |

## 4. Fix

**The mechanism, not the ten call sites** (`fix-bug-rule.md` §2). The defect was not "one test
mocks the wrong method" — it was "four test files each held their own copy of the knowledge of how
the CLI reaches the dispatcher, and one of those copies going stale hangs the gate".

`tests/unit/modules/market_data/cli/dispatching_app.py` — one helper, `dispatching_app()`, that
builds an `App` whose container resolves `ICommandDispatcher` to a dispatcher the test controls,
with `raises` / `success` / `message` options. All four test files use it. Resolving any other port
raises `KeyError` deliberately: **a wrong resolve should be loud, not plausible.** The next change
to that seam breaks one import instead of five mocks, and the file that can hang cannot be the one
that is forgotten.

`test_stream_cmd.py` also gained a case for the refusal branch (`success=False` must `sys.exit(1)`
*before* the loop) — the one path that returns a response and still must not reach `while True`.

Its module docstring now records why the success path is deliberately uncovered and that a future
change to the dispatch seam must update the fixture in the same commit.

## 5. Regression test

`tests/unit/modules/market_data/cli/` — 16 tests, **0.76 s**, all green.

The reproduction is inherent rather than asserted: before the fix,
`pytest tests/unit/modules/market_data/cli/test_stream_cmd.py` never terminates (confirmed with
`timeout 45` → `Terminated`); after it, the same file completes in under a second. A test asserting
"this does not hang" is not writable without a timeout mechanism, which §6 recommends adding.

## 6. The durable gap this exposed, and what should still be done

**`pytest-timeout` is not installed, so a hanging test is silent.** That is the reason a 15-line
mistake cost an afternoon: the failure mode was not "a test fails" but "the gate goes quiet", which
looks identical to "the gate is slow" and gives no traceback, no test name and no exit code.

Recommended as its own change (not done here — it edits dependencies and the gate script, which is
outside PR 0.4a-2's scope): add `pytest-timeout` and set a per-test timeout in
`[tool.pytest.ini_options]` generous enough for the slowest legitimate test. Any future hang then
arrives as a normal failure with a stack trace pointing at the offending test, instead of as a
stalled gate that needs `py-spy` and a comparison of log byte counts to diagnose.

Two smaller notes for whoever next debugs a quiet gate:

- `ps`'s `%CPU` is an average over the process's whole lifetime, not an instantaneous reading.
  During this stall it showed idle workers at 40-95%, which reads as "busy" and is misleading. Use
  `py-spy dump` — on **every** worker.
- The test named last on the console is whichever one was in flight, not the cause. Three runs named
  two different tests; both passed in isolation.
