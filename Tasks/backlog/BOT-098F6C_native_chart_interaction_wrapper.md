# BOT-098F6C — Native Backtest interaction wrapper

**Parent:** [`BOT-098F6`](BOT-098F6_backtest_chart_host_migration.md)  
**Depends on:** `BOT-098F6B` ✅  
**Priority:** P1  
**Complexity:** L / Performance-specialized  
**Status:** Backlog

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
