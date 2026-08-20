# BUG-015 — Native chart intermittently rebuilds OHLCV/volume geometry during plain pointer interaction (real Windows evidence)

**Reported:** 2026-08-19, while verifying whether `BOT-098F4`/`BOT-098F5`/`BOT-098F6C`'s
Windows-only acceptance criteria could finally be satisfied on a real Windows
machine.
**Severity:** P2 — violates an explicit acceptance criterion
(`BOT-098F6C` #4: "leaves OHLCV, volume, indicator and marker geometry-build
counts unchanged unless a documented LOD/resize boundary is crossed"), but is
a wasted-work/performance concern, not a visual-correctness one — the
rebuilt geometry is still correct, just unnecessarily recomputed.
**Status:** Open — root cause narrowed to one function, not confirmed

## Context

`Tasks/ROADMAP.md` carried a note saying real Windows GPU/RHI pixel-color and
FPS evidence for `BOT-098F4`/`F5`/`F6C` "could not be produced" from the
Linux dev machine this project had been using. Asked to verify that on a real
Windows machine and delete the note if resolved.

Verifying it surfaced three unrelated **probe-script** bugs (fixed the same
session — see the commit touching
`scripts/benchmarking/native_backtest_chart_interaction_probe.py`: an
identical-position hover retry that could never re-trigger a Qt move event,
an FPS read that happened before the native code's own 500ms measurement
window had elapsed, and a marker fixture pinned to a price permanently
outside every viewport the probe visits). Fixing those revealed *this*
separate, real finding underneath.

## Symptom

Running the fixed
`scripts/benchmarking/native_backtest_chart_interaction_probe.py` repeatedly
on a real Windows 11 machine (confirmed genuine Direct3D11 RHI backend, not
software rendering — `QQuickView.rendererInterface().graphicsApi() ==
GraphicsApi.Direct3D11`):

```
=== run 1 ===  ohlcv: false   volume: false   indicator: true
=== run 2 ===  ohlcv: true    volume: true    indicator: true
=== run 3 ===  ohlcv: false   volume: false   indicator: true
=== run 4 ===  ohlcv: false   volume: false   indicator: true
```

(`false` = geometry-build count changed between before/after a plain
drag+wheel+hover sequence — i.e. it rebuilt.) 3 of 4 runs show OHLCV and
volume geometry rebuilding during interaction that should only ever change
the camera/paint transform, never the underlying vertex buffers. `indicator`
never shows this — but the probe's fixture never submits any indicator data,
so `indicatorsMatchCandles` is always false there and that geometry path
is never meaningfully exercised; its "unchanged" reading is not evidence of
anything.

## Investigation so far

`native/chart_renderer/native_chart_item.cpp`'s `updatePaintNode()`:

```cpp
const QSizeF currentSize(width(), height());
const bool sizeChanged = root->renderedSize != currentSize;
...
if (snapshotChanged || sizeChanged) {
    populateGeometry(...);
    ++root->buildCount;
}
```

OHLCV geometry rebuilds on exactly two conditions: a new data snapshot, or
`sizeChanged` — an **exact** `QSizeF` inequality against the item's own
`width()`/`height()`. Nothing in the probe calls `resize()` mid-interaction
(the window is sized once, before any data is submitted), so a genuine,
intentional resize is not expected during the measured window. `sizeChanged`
being intermittently true, without deliberately triggering it, is the
leading hypothesis — but **not confirmed**: I have not yet instrumented the
native code to print `width()`/`height()` per paint call, which would confirm
or rule this out directly (nothing else in `updatePaintNode()` sets
`root->buildCount`).

Volume's own rebuild condition additionally includes a viewport-width-driven
LOD bucket-size check, which the acceptance criterion explicitly allows to
legitimately change on zoom — so volume rebuilding on its own would not be
surprising. OHLCV has no such allowance, and its rebuild condition is only
`snapshotChanged || sizeChanged`, so its involvement here specifically
implicates `sizeChanged`.

## Suggested next step (not yet attempted)

Add a temporary debug log (`qDebug()`) inside `updatePaintNode()` printing
`currentSize`, `root->renderedSize`, and the three boolean flags on every
call, rebuild via `.\scripts\build-native-chart.ps1`, and re-run the probe
until a rebuild reproduces — this will show directly whether `sizeChanged` is
the trigger and, if so, what `currentSize` actually was compared to the
previous frame's. Do not guess further without that print; the source of a
sub-pixel or rounding-driven size fluctuation (if that is what this is) could
be anywhere in the QML layout chain (`anchors.fill: parent` on `NativeChartItem`
inside `NativeBacktestChart.qml`, itself inside whatever `QQuickWidget`
container `NativeBacktestChartHost` constructs) and needs to be traced
outward from a confirmed trigger, not guessed inward.

## Reproduction

```powershell
.\scripts\build-native-chart.ps1
$env:PYTHONPATH = ".."
python -m Sagittarius_Elite_Warrior.scripts.benchmarking.native_backtest_chart_interaction_probe
```

Run several times in a row; ~75% show `"geometry_retained_across_camera_and_pointer_interaction"`
with `"ohlcv": false, "volume": false`.
