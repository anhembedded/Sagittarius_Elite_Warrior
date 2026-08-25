# BUG-049 — `binance_fake_server.py`'s background thread leaves 5 uncollectable GC objects at interpreter shutdown

**Reported:** 2026-08-25, found while building `EPIC-009` D6's fake Binance
server and verifying the Sanity tier's own log output for problem-level noise
(the same discipline `diagnostic_guard` exists to enforce).
**Severity:** 🟢 P3 — does not fail any test, does not affect `pytest`'s exit
code, and is not evidence of an unbounded leak (`5` is fixed, not growing per
test — `booted_app` is session-scoped, so the fake server starts exactly once
per pytest process regardless of test count).
**Status:** 🔴 Open — investigated, not root-caused; same shape as `BUG-030`
(*"chưa bisect ra nguồn chính xác"*), same honesty about the gap.

## Symptom

```
gc:0: ResourceWarning: gc: 5 uncollectable objects at shutdown; use gc.set_debug(gc.DEBUG_UNCOLLECTABLE) to list them
```

Printed by the interpreter itself at process teardown, after pytest's own
`24 passed` summary line — not a captured `pytest` warning, not something
`conftest.py`'s `diagnostic_guard` can see (it fires after the test session,
not during any one test).

## What was ruled out

**Not `tests/sanity/binance_fake_server.py`'s `run_binance_fake_server()`
alone.** Isolated with `gc.set_debug(gc.DEBUG_SAVEALL)` around exactly one
enter/exit of the context manager, outside pytest, outside the Qt app, outside
everything else this session boots:

```python
gc.collect()
with run_binance_fake_server() as url:
    ...
gc.collect(); gc.collect()
print(len(gc.garbage))   # 0
```

Zero garbage. So the leak is not in the `HTTPServer`/`threading.Thread`
combination by itself — it is an **interaction** with something else already
alive in the full Sanity session (most likely the Qt event loop / `AsyncRuntime`
background thread `booted_app` also starts, given both are running background
threads concurrently, but this is a hypothesis, not confirmed).

**Not fixed by an explicit `gc.collect()`** added to
`run_binance_fake_server()`'s teardown (attempted, verified ineffective —
count stays at 1 occurrence / 5 objects with or without it). Left in place
regardless since immediate collection at the point of teardown is harmless and
arguably still correct practice; it just is not this bug's fix.

**Confirmed introduced by this session's D6 work**, not pre-existing — A/B
verified: `git stash` (removing `binance_fake_server.py` and its wiring)
against an otherwise identical sanity run showed 0 occurrences; restoring it
showed 1.

## Why this is worth fixing eventually, not just tolerating

`ci-local.ps1`'s `Invoke-RunLogScan` greps for `- (WARNING|ERROR|CRITICAL) -`,
Python `logging`'s own format. This message is a raw `print()` from the `gc`
module at shutdown, in a different format — it would slip through the exact
same gate `BUG-028`/`BUG-031` slipped through (Qt messages, a different
channel `Invoke-RunLogScan` also cannot see). Low severity now because the
count is small and fixed, but a channel nothing scans for is a channel that
can grow silently.

## Next step, not done here

Reproduce with `gc.set_debug(gc.DEBUG_SAVEALL)` wrapped around the *whole*
Sanity session (not just the fake server in isolation) and inspect
`gc.garbage`'s actual contents to identify the real cycle, rather than
guessing at the interaction. Out of scope for landing D6 — this is a
diagnostic-noise cleanup, not a correctness defect, and D6's own tests
(`tests/sanity/test_composition_root.py`) are green.
