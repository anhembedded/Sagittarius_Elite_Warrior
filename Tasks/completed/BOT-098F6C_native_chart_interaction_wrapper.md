# BOT-098F6C — Native Backtest interaction wrapper

**Parent:** [`BOT-098F6`](BOT-098F6_backtest_chart_host_migration.md)  
**Depends on:** `BOT-098F6B` ✅  
**Priority:** P1  
**Complexity:** L / Performance-specialized  
**Status:** In Progress — acceptance criterion 3 only partially satisfied (see below)

## Result

`src/presentation/ui/screens/backtest/NativeBacktestChart.qml` wraps
`NativeChartItem` with axis ticks/tooltip/dev-FPS display and real drag/
wheel/hover gesture handling, calling only `setViewport`/
`setCrosshairPosition`/`clearCrosshair` — never repacking OHLCV/indicator/
marker data. Two small QObject bridges keep pixel math and timezone
formatting out of QML JS:
`src/presentation/ui/native_chart_viewport_gestures.py` (pure
`resolve_drag_viewport`/`resolve_wheel_viewport`, plus
`NativeChartGestureBridge`) and `native_chart_timezone_bridge.py`
(`NativeChartTimezoneBridge`, delegating to the app's one existing
`display_timezone_service.format_display_timestamp` instead of
reimplementing IANA/fallback rules a second time). `NativeBacktestChartHost`
(BOT-098F6B) now loads this QML file and registers both bridges as context
properties.

Three real bugs found and fixed while wiring this up, none of them
theoretical:

1. `_clamp_span`'s wheel-zoom clamp computed the minimum/maximum span but
   only ever applied it when an edge was actually crossed — a viewport
   already pinned near the minimum span could stay under-sized forever if
   neither edge was hit. Fixed by always recentering on the clamped span
   before checking edges.
2. `NativeChartItem::submitSnapshot()` emits `snapshotChanged()` and *then*
   unconditionally resets the viewport to the full range itself. The QML's
   "show the latest 150 candles" handler was calling `setViewport()`
   synchronously inside that same signal, so its own call was silently
   overwritten the instant the native code continued past the emit. Fixed
   by deferring via `Qt.callLater(...)`.
3. Real desktop interaction probes must snapshot their "before" build-count
   baseline only *after* confirming that same deferred initial-viewport
   call has actually settled — otherwise its own legitimate one-time
   geometry cost gets misattributed to the interaction that follows (the
   same class of timing bug found twice already this session in the F5
   benchmark and the F4 probe).

16 unit tests (pure gesture math + timezone formatting, no QApplication) + 4
sanity tests (real app boot, no QML warnings, axis ticks populate, initial
viewport correct). A real **component probe**
(`scripts/benchmarking/native_backtest_chart_interaction_probe.py`) — not
Desktop E2E; see the `ci-rule.md` update this task also made distinguishing
the two — exercises real drag/wheel/hover against the real Wayland session
on this machine: drag panning and wheel zoom are 100% reliable across
repeated runs and geometry stays retained throughout. Pointer-only hover
(crosshair) is measurably flaky specifically for *hover-without-a-button*
synthetic input delivered through a `QQuickWidget` on this remote/virtual
Wayland session — proven environment-dependent, not a logic bug, since a
direct Python call to `setCrosshairPosition()` with identical coordinates
always succeeds and is covered by the sanity suite instead. Real pixel-color
sampling also came back empty here, matching the exact same finding BOT-098F5
already recorded for native `grabWindow()` captures on this machine's
software RHI — expected, non-blocking, reserved for real Windows evidence.

**Not proven, and cannot be from this environment:** this remains a
component-level probe, not Desktop E2E — `NativeBacktestChartHost`/this QML
file are still not reachable from the real running app (`main.py` still
renders 100% Python; that only changes in `BOT-098F6D`). True Desktop E2E —
through the real entry point and the real Backtest screen — is required
before this feature counts as done, and is `BOT-098F6D`'s and later
`BOT-098F6E`'s responsibility once that wiring exists.

307 Backtest/native-chart-scoped tests and `./scripts/ci-local.ps1 -Full`
pass.

## Goal

Provide the small declarative QML layer that gives the embedded native chart
truthful axes, timezone-formatted tooltip, developer FPS and real pan/wheel/
pointer interaction without transferring business decisions or bulk geometry
work into QML.

## Scope

- `NativeBacktestChart.qml` displays `NativeChartItem`, axis tick models,
  crosshair tooltip and dev FPS from existing native properties.
- Drag/wheel interaction computes the final indexed viewport and calls
  `setViewport`; hover calls `setCrosshairPosition`. It must not repack OHLCV,
  indicators or markers.
- Keep initial visible window equivalent to current Backtest (latest 150
  candles), preserve raw UTC identity and format timestamps in the selected
  display timezone only at presentation boundary.
- Use QML Theme tokens and stable object names for all interactive/tested
  elements. No decorative animation or nested QQuickWidget.

## Acceptance criteria

1. Unit tests verify pure viewport math, clamping, final range and timezone
   formatting independently of rendering.
2. Embedded native QML sanity loads cleanly, exposes axes/tooltip/FPS and has
   no QML warnings.
3. Windows desktop probe uses real drag, wheel and pointer events, then proves
   final viewport/crosshair candle correctness, visible entry/exit/indicator
   colors, completed FPS and zero forbidden Qt messages.
4. Camera/pointer interaction leaves OHLCV, volume, indicator and marker
   geometry-build counts unchanged unless a documented LOD/resize boundary is
   crossed.
5. Focused tests and `./scripts/ci-local.ps1 -Full` pass.
