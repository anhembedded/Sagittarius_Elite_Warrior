# BUG-049 — `binance_fake_server.py`'s background thread leaves 5 uncollectable GC objects at interpreter shutdown

**Reported:** 2026-08-25, found while building `EPIC-009` D6's fake Binance
server and verifying the Sanity tier's own log output for problem-level noise
(the same discipline `diagnostic_guard` exists to enforce).
**Severity:** 🟢 P3 — does not fail any test, does not affect `pytest`'s exit
code, and is not evidence of an unbounded leak (`5` is fixed, not growing per
test — `booted_app` is session-scoped, so the fake server starts exactly once
per pytest process regardless of test count).
**Status:** ✅ Root-caused & closed 2026-08-25 — no code fix applies. The
cycle is a PySide6/shiboken metaobject-system characteristic, not something
`binance_fake_server.py`'s own code creates or could release. See §2.

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

## 2. Root cause (2026-08-25) — identified via `gc.DEBUG_UNCOLLECTABLE`

Reproduced the exact symptom first, on a clean environment (`24 passed, 2
warnings` then `gc:0: ResourceWarning: gc: 5 uncollectable objects at
shutdown`). Two probes, both confirming the same thing:

1. `atexit.register`-based probe (registered before `pytest.main()`, so it
   runs last among the interpreter's own atexit hooks): a forced
   `gc.collect()` at that point finds **0** garbage. Same negative result
   `run_binance_fake_server()`'s own teardown `gc.collect()` already got —
   confirmed independently. **The 5 objects are not reachable-but-uncollected
   Python garbage at any point Python code can hook into; they only become
   garbage during CPython's own internal `_PyGC_Fini` finalization pass**,
   strictly after every `atexit` callback has already run.
2. `gc.set_debug(gc.DEBUG_UNCOLLECTABLE)` set from interpreter start (`python
   -c "import gc; gc.set_debug(...); import pytest; pytest.main(...)"`):
   prints every object any collection pass (mid-session or at shutdown)
   found uncollectable. The types printed, verbatim:

   ```
   PySide6.QtCore.Property, PySide6.QtCore.QMetaObject, Shiboken.ObjectType,
   SourceFileLoader, ModuleSpec, function, cell, dict, list, tuple
   ```

   This is the textbook shape of a **PySide6/shiboken Qt-Property metaobject
   cycle**: a `QtCore.Property(...)`-decorated getter/setter pair closes over
   its owning class (`cell`/`function`), the `Property` descriptor holds
   those closures, and the class's `QMetaObject`/`Shiboken.ObjectType` links
   back to the descriptor — a cycle that spans the Python/C++ boundary.
   Python's cyclic GC can only break cycles it can fully see and `tp_clear`;
   the C++-side half of this one is opaque to it, which is exactly what
   "uncollectable" (as opposed to merely "not yet collected") means.

   This is a documented characteristic of PySide6/shiboken's binding of Qt
   properties, not something `binance_fake_server.py`'s `HTTPServer`/
   `threading.Thread` pair creates — `run_binance_fake_server()` holds no
   `QObject`, no `Property`, nothing PySide6 touches.

**Reconciling with §1's A/B result:** the earlier finding that `git stash`ing
D6's wiring drops the warning to 0 occurrences is still accurate, but it does
not mean D6's code is the cycle's *source*. `Property`-bearing `QObject`
instances already exist on every Sanity boot (any presenter/view-model in
`sagittarius_engine.extensions.pyside_mvc`) regardless of D6. What D6 changes
is whether `app.boot()` reaches the code paths that construct the specific
`QObject`s carrying this cycle at all (previously it hung/failed against the
real network per `BUG-045`, before ever getting there) — D6 doesn't create
the cycle, it's what makes the boot complete far enough for a pre-existing
one to surface.

**No code fix applies.** The cycle lives entirely inside PySide6/shiboken's
own C++↔Python bridge; there is no application-level `__del__`, reference, or
callback to remove. Silencing the warning (a `warnings.filterwarnings` for
`ResourceWarning` here) would hide the signal rather than fix anything, and
was deliberately not done. Closing as investigated and understood: severity
stays P3 (fixed count, no growth, no effect on `pytest`'s exit code), the
`ci-local.ps1` blind-spot noted in §1 stands as a known limitation (this
channel still isn't scanned), but there is nothing left to root-cause.
