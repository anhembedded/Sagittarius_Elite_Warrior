# BOT-098F6B — Native chart adapter and snapshot contract

**Parent:** [`BOT-098F6`](BOT-098F6_backtest_chart_host_migration.md)  
**Depends on:** `BOT-098F6A` ✅, `BOT-098F4` (unit/sanity scope only — F4's Windows Desktop E2E gap did not block this)  
**Priority:** P1  
**Complexity:** L  
**Status:** Completed

## Result

`src/presentation/ui/screens/backtest/logic/native_backtest_chart_adapter.py`
adds the standalone pieces, none wired into production selection yet
(that's `BOT-098F6D`):

- `timestamp_seconds_to_ms` / `resolve_candle_index_for_timestamp_ms`
  (exact-match only — a marker silently snapped to the nearest candle would
  misreport when an order actually filled).
- `build_native_ohlcv_arrays` merges Backtest's separately-tracked candle/
  volume series; `build_native_indicator_series` forward-fills sparse
  timestamp-keyed samples into the ABI's required dense array, rejecting an
  unfillable leading gap or non-finite value; `build_native_marker`
  converts a Python `MarkerPoint` into the enum-typed, candle-index-based
  `NativeChartMarker`, rejecting an unaligned timestamp or unknown label/
  direction. Strict-monotonic timestamp enforcement stays owned by
  `pack_native_ohlcv_snapshot` — the conversion step doesn't duplicate it.
- `NativeChartSubmissionFence`: rejects a caller-supplied
  `(action_id, generation)` token that isn't strictly newer than the last
  accepted one, so a late callback from a superseded run can't reach the
  native item even if its data happens to be the same shape.
- `NativeBacktestChartHost.create()` builds the QQuickWidget via the app's
  real `create_quick_widget()` (not a dev-only shortcut) and
  `configure_native_chart_engine(..., required=True)`, raising the
  already-established `NativeChartRuntimeError` on any construction/ABI
  failure — a future factory can catch that specific type to fall back to
  Python. Found and fixed a real lifetime bug during this work: `component`/
  `root_item` need an explicit Python-side owner for the process lifetime of
  the host, or the underlying C++ `NativeChartItem` gets deleted out from
  under it the moment `create()` returns and its locals go out of scope.
  `_assert_owning_gui_thread()` raises `RuntimeError` (loud, not the silent
  `False` the C++ layer uses) the instant any submit method is called off
  the widget's own thread.

19 unit tests (pure conversion/fencing, no QApplication needed) + 3 sanity
tests (real app boot via the same `booted_app` fixture pattern as
`test_backtest_screen_ui_sanity.py`, covering construction, real snapshot
submission with revision/count diagnostics, and worker-thread rejection).
265 Backtest-scoped tests and `./scripts/ci-local.ps1 -Full` pass.

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
