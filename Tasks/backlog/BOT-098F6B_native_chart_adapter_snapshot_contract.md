# BOT-098F6B — Native chart adapter and snapshot contract

**Parent:** [`BOT-098F6`](BOT-098F6_backtest_chart_host_migration.md)  
**Depends on:** `BOT-098F6A` ✅, `BOT-098F4`  
**Priority:** P1  
**Complexity:** L  
**Status:** Backlog

## Goal

Create a Backtest native host that constructs `NativeChartItem` inside an
embedded `QQuickWidget` and converts Backtest data into the existing immutable
native snapshot ABIs. The host is not selected by production config in this
phase.

## Scope

- Build `QQuickWidget` with `create_quick_widget()`, configure its exact engine
  with `configure_native_chart_engine()` before QML parsing, and retain the
  native item only on its owning GUI thread.
- Implement UTC-second to strict UTC-millisecond mapping, monotonic revisions,
  timestamp-to-index lookup, integrated volume, dense finite price-overlay
  indicator conversion and truthful LONG entry/exit marker conversion.
- Fence every submission with action/preview generation supplied by the caller.
  Native ABI count equality alone is insufficient when equal-sized snapshots
  originate from different runs.
- Construction/runtime/ABI failure returns a typed diagnostic to the future
  factory; no production fallback wiring here.

## Acceptance criteria

1. Tests reject duplicate/non-monotonic converted timestamps, non-finite or
   sparse-unfillable indicator data, unaligned marker timestamps, stale
   action/preview generation and non-increasing local revisions.
2. Embedded QQuickWidget sanity proves the native module parses with the real
   theme/import setup and does not rely on dev-only environment initialization.
3. Native item receives candle, indicator and marker snapshots on its owning
   UI thread; diagnostics show the expected revisions/counts.
4. No `NativeChartItem` or QSG node is touched by a worker callback.
5. Focused unit/sanity tests and `./scripts/ci-local.ps1 -Full` pass.
