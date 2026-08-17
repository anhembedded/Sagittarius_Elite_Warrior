# BOT-098F3 — Native retained volume and indicator buffers

**Parent:** `BOT-098F`  
**Depends on:** `BOT-098F1`, `BOT-098F2`, `BOT-098F2A` ✅  
**Priority:** P1  
**Status:** Completed

## Goal

Extend `NativeChartItem` with retained GPU geometry for the OHLCV volume
series and price-overlay indicators.  This slice remains an isolated native
renderer; it does not replace the production PyQtGraph Backtest chart.

## Boundary contract

- OHLCV snapshot ABI v1 stays unchanged. It already transports volume; native
  parsing must retain and render it rather than discard it.
- Indicators use a separate versioned, immutable contiguous binary snapshot.
  It must match the active candle count, carry monotonic revision and reject
  non-finite values before crossing into the render thread.
- Volume keeps total source values. Its renderer only changes pixels, not
  market data or Backtest semantics.
- Indicator LOD is an envelope per physical pixel column: min/max extrema are
  retained at distant zoom; sparse views retain exact values. Device pixel
  ratio belongs in this geometry budget, not marker readability capacity.
- Camera-only updates keep retained geometry when the selected LOD and cache
  window remain valid; later marker/crosshair work must not rebuild these
  buffers on every pointer move.

## Required proof

1. Serializer/unit tests for snapshot layout, color/value alignment and
   rejection paths.
2. Native QML sanity for volume and multi-line indicator diagnostics.
3. Windows visual probe samples candle, volume and indicator colors at DPR 1+
   and asserts no Qt render warnings.
4. Semantic tests preserve volume totals and indicator peak/trough values at
   dense LOD, then restore exact samples when zoomed in.
5. Native build and `scripts/ci-local.ps1 -Full` pass.

Performance evidence: [`BOT-098F3 native volume and indicator performance`](../reports/BOT-098F3_native_volume_indicator_performance.md).

## Outcome

- Native OHLCV snapshot v1 now retains and renders volume with two batched
  retained geometry nodes; the ABI itself did not change.
- A separate immutable indicator snapshot ABI carries aligned color/value
  planes into the native render thread, with stale/misaligned/non-finite input
  rejected at the boundary.
- Indicator min/max envelopes use physical output columns and the active DPR.
  Marker readability intentionally remains logical-pixel based.
- Full CI: native CMake, Ruff, 1,026 primary tests and 28 sanity tests passed;
  coverage is 94.10%.
