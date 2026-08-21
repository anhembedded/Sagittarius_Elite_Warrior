# BUG-015 — Native chart intermittently rebuilds OHLCV/volume geometry during plain pointer interaction (real Windows evidence)

**Reported:** 2026-08-19, while verifying whether `BOT-098F4`/`BOT-098F5`/`BOT-098F6C`'s
Windows-only acceptance criteria could finally be satisfied on a real Windows
machine.
**Severity:** P2 — violates an explicit acceptance criterion
(`BOT-098F6C` #4: "leaves OHLCV, volume, indicator and marker geometry-build
counts unchanged unless a documented LOD/resize boundary is crossed"), but is
a wasted-work/performance concern, not a visual-correctness one — the
rebuilt geometry is still correct, just unnecessarily recomputed.
**Status:** ✅ **Fixed 2026-08-21** — root-caused with real qWarning
instrumentation on a real Windows 11 / Direct3D11 / NVIDIA RTX 3060 session,
mutation-verified (10/10 → then 15/15 clean runs after fix, vs. ~25% before).
**Turned out not to be a native rendering bug at all** — see Root cause.

## Symptom

Running `scripts/benchmarking/native_backtest_chart_interaction_probe.py`
repeatedly on a real Windows 11 machine (confirmed genuine Direct3D11 RHI
backend, not software rendering — `QQuickView.rendererInterface().graphicsApi()
== GraphicsApi.Direct3D11`):

```
=== run 1 ===  ohlcv: false   volume: false   indicator: true
=== run 2 ===  ohlcv: true    volume: true    indicator: true
=== run 3 ===  ohlcv: false   volume: false   indicator: true
=== run 4 ===  ohlcv: false   volume: false   indicator: true
```

(`false` = geometry-build count changed between before/after a plain
drag+wheel+hover sequence.) ~75% of runs showed OHLCV/volume "changed".

## Root cause

The original hypothesis (`native_chart_item.cpp`'s `updatePaintNode()`
rebuilding geometry due to a spurious `sizeChanged`) was **disproven**, not
confirmed. Investigation method: added a temporary `qWarning()` (not
`qDebug()` — the probe script's own `qInstallMessageHandler` silently drops
`QtDebugMsg`, only `QtWarningMsg`/`QtCriticalMsg` reach its captured
`qt_warnings` list) inside `updatePaintNode()`, printing `currentSize`,
`renderedSize`, `sizeChanged`, and `root->buildCount` on every call, rebuilt
via `.\scripts\build-native-chart.ps1`, and ran the probe repeatedly capturing
the trace for both passing and failing runs.

**Result: `root->buildCount` never exceeded `1` in any run, passing or
failing.** The cold-start build increments it once (`renderedSize` goes from
its uninitialized `(-1,-1)` to the real size); every single call after that
had `sizeChanged=false` and `buildCount` stayed at `1` for the entire
interaction sequence — drag, wheel, and hover included. The native rendering
code was never rebuilding anything redundantly.

The real mechanism: `updatePaintNode()` runs on the Qt Quick **render
thread** and captures `root->buildCount` there
(`native_chart_item.cpp:1347`), then hands it to
`publishRenderDiagnostics()` via `QMetaObject::invokeMethod(this, lambda)`
— an implicit cross-thread hop to the **GUI thread**, where it's finally
written into the `geometryBuildCount_` member backing the
`Q_PROPERTY(quint64 geometryBuildCount ...)` that Python/QML actually reads
(`native_chart_item.cpp:1610-1615`; there's also a stale-revision guard there
that drops out-of-order updates entirely, compounding the same class of
race). The probe script's `_geometry_build_counts()` reads that property
directly from Python. Its "before" baseline was captured after only a fixed
number of `app.processEvents()` calls (`for _ in range(20): ...`) — which
drains whatever is *already* posted to the GUI thread's queue, but does not
wait for the render thread to have actually finished its first paint and
posted that queued call yet. On ~75% of runs, the baseline read landed
**before** that first publish arrived, so it read the property's
uninitialized default (`0`) instead of the true, already-correct value
(`1`) — and the "after" snapshot (captured following  further interaction
and more `processEvents()` churn) then correctly read `1`, making the probe
report "changed" (`0 != 1`) for a value that was actually stable the entire
time. Confirmed directly: `buildCount` in the render-thread trace was `1`
before *and* after the interaction on every single failing run examined —
only the GUI-thread property's read timing differed.

This is the same class of bug as three other probe-script issues already
found and fixed in this same investigation (an identical-position hover
retry that could never re-trigger a move event, an FPS read taken before its
own 500ms measurement window elapsed, a marker fixture pinned outside every
visited viewport) — and structurally identical to the FPS one specifically:
that fix already had to wait for a real post-condition (`>=500ms` of
real elapsed time between two `afterRendering` firings) rather than trusting
a fixed iteration count, for exactly the same render-thread/GUI-thread timing
reason.

## Fix

`scripts/benchmarking/native_backtest_chart_interaction_probe.py`: replaced
the fixed `for _ in range(20): app.processEvents()` warm-up before capturing
`geometry_before_interaction` with a real poll loop (up to 2s, `10ms` steps)
that waits for `geometryBuildCount > 0 and volumeGeometryBuildCount > 0` —
i.e. waits for the cold-start build's diagnostics to have actually landed on
the GUI thread, not just for a fixed number of GUI-thread event-loop turns.
Raises `SystemExit` with a clear message if that never happens within 2s
(distinguishing "diagnostics are just slow to publish" from "the cold-start
build itself is broken", which would be a real bug worth its own report).

No native C++ changes were needed or made — the temporary `qWarning()`
instrumentation added for diagnosis was fully reverted before this fix; `git
diff` on `native/chart_renderer/native_chart_item.cpp` is empty.

## Regression test / verification

Not a unit test (this is Windows-desktop-only opt-in evidence, per the
script's own docstring — no headless equivalent exists). Verified by direct
repeated execution on the real machine that reproduced the bug:

- **Before fix:** ~25% pass rate (matches the original report's 1/4 sample).
- **After fix, exit-code based (script's own internal assertions, all
  criteria including the separately-known `indicator` caveat):** **15/15
  clean runs**, `$LASTEXITCODE -eq 0` every time.
- Root cause confirmed via the qWarning trace itself, not inferred: same
  trace method re-run after the probe fix showed `geometryBuildCount`/
  `volumeGeometryBuildCount` already non-zero by the time the "before"
  baseline was captured, on every run.

## Note on the acceptance criterion this was blocking

`BOT-098F6C` criterion #4 ("leaves OHLCV, volume, indicator and marker
geometry-build counts unchanged unless a documented LOD/resize boundary is
crossed") is **satisfied by the actual native rendering code** — it always
was. The violation reported here was entirely an artifact of the probe's own
measurement race, not a real wasted-recompute regression in the shipped
renderer. Whoever revisits `BOT-098F4`/`F5`/`F6C`'s acceptance status should
treat this criterion as met, not as still-open pending further rendering
work.
