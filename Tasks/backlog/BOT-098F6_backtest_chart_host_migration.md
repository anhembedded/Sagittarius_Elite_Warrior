# BOT-098F6 — Backtest native chart-host migration with Python fallback

**Parent:** [`BOT-098F`](BOT-098F_qt_quick_scene_graph_chart_renderer.md)  
**Depends on:** `BOT-098F4`, `BOT-098F5`  
**Priority:** P1  
**Complexity:** L / Performance-specialized  
**Status:** Backlog

## Goal

Move the Backtest OHLC interaction path from Python `ChartCard` to the retained
C++ `NativeChartItem` while keeping a configuration-selectable Python fallback
for one release. The Backtest View and Presenter must depend on a narrow shared
chart-host contract, not on either renderer implementation.

## Scope

Native scope in this slice:

- OHLC candles, integrated volume, price-overlay indicators, truthful trade
  entry/exit markers, crosshair/tooltip, timezone-formatted axes, pan/zoom and
  dev FPS;
- immutable monotonic snapshots and `action_id`/preview fencing at the adapter;
- `BacktestChartControls` and timeframe toolbar remain QtWidgets header controls
  so the user-facing Backtest workflow does not change.

Outside scope for this slice:

- Dev Board / live chart migration;
- line/area/Heikin-Ashi implementations in C++;
- equity-only and BOTH subplot native parity, script regions, script info and
  arbitrary script marker text. These modes must select the Python host until
  their native contracts exist; they may never silently lose visual data.

## Architecture contract

1. Define a Backtest-scoped `Protocol`/port with only the operations used by
   the Backtest screen. It owns widget exposure, chart header controls, data
   submission, overlays/markers, timeframe signal, visibility toggles,
   diagnostic state and deterministic cleanup.
2. `PythonBacktestChartHost` wraps the existing `ChartCard` without rewriting
   ChartCard internals. `NativeBacktestChartHost` owns a `QQuickWidget` created
   through `create_quick_widget()`, calls `configure_native_chart_engine()`
   before QML parsing, and hosts `NativeChartItem` through a small declarative
   QML wrapper.
3. `BacktestChartHostFactory` is a transient DI-resolved factory. It selects
   host once per BackTestView construction from `backtest.chart.backend =
   python|native|auto` and optional `SAGITTARIUS_BACKTEST_CHART_BACKEND`.
   A widget/host is never singleton, shared across views or hot-swapped while
   visible.
4. `native` or `auto` resolves native only after compatible runtime discovery.
   Missing plugin/ABI mismatch/construction or submission failure must create
   the Python host and emit one actionable warning; no blank chart.
5. `NativeBacktestChartAdapter` runs on the UI thread. It owns monotonic
   revisions, UTC-ms timestamp-to-candle-index mapping, dense finite aligned
   indicator conversion, marker semantic conversion and pending action/preview
   generation checks before invoking the native item.
6. QML owns only gesture-to-viewport conversion and presentation formatting.
   It must not duplicate data/indicator/business decisions. Camera and pointer
   updates may not rebuild bulk geometry.

## Required child phases

`BOT-098F6` is an umbrella only. It may not be implemented as one change. Each
child task must finish its own focused tests and its acceptance criteria before
the next child starts:

| Child | Goal | Required proof before the next phase |
| --- | --- | --- |
| [`BOT-098F6A`](BOT-098F6A_backtest_chart_port_and_python_adapter.md) | Extract the Backtest-only host port, Python adapter and transient factory while preserving the Python renderer exactly. | Unit/Backtest integration prove the same toolbar, modes, indicators and markers; full CI green. |
| [`BOT-098F6B`](BOT-098F6B_native_chart_adapter_snapshot_contract.md) | Add the main-thread native snapshot adapter and QQuickWidget construction/runtime fallback. No production selection yet. | Unit tests reject stale/misaligned/non-finite conversion; QML sanity constructs in embedded QQuickWidget; full CI green. |
| [`BOT-098F6C`](BOT-098F6C_native_chart_interaction_wrapper.md) | Add the declarative QML gesture/axis/tooltip/FPS wrapper and native OHLC interaction contract. | Desktop probe sends real pan/wheel/pointer input, verifies final viewport/crosshair and retained geometry; no Qt warnings; full CI green. |
| [`BOT-098F6D`](BOT-098F6D_backtest_native_opt_in_cutover.md) | Wire config + DI selection into Backtest for supported OHLC scope, retain explicit capability fallback. | Integration proves Python/native selection and unsupported-mode fallback; F5 DPR1/DPR2 report; full CI green. |
| [`BOT-098F6E`](BOT-098F6E_native_default_rollout.md) | Change default only after a stable release, retain emergency Python override. | One-release production evidence, Python kill-switch regression and desktop E2E green. |

## Acceptance criteria

1. Each child phase is independently testable and cannot silently expand into a
   later phase's concern.
2. BackTestView/Presenter reach the renderer only through the host port; only
   factory/host modules import concrete `ChartCard` or `NativeChartItem`.
3. Native snapshot submission rejects stale/misaligned/non-finite data before
   render; stale `action_id` or preview updates cannot overwrite a newer view.
4. Pan, wheel zoom and crosshair use real input on the QQuickWidget host and do
   not rebuild candle/volume/indicator/marker buffers on camera-only movement.
5. Timezone ticks/tooltip and `LONG_ENTRY`/`LONG_EXIT` semantics remain
   truthful; native mode never makes unsupported equity/script detail disappear
   silently.
6. Native becomes default only in `F6E`, after F5 evidence and all focused
   child-phase checks are green. Python stays fallback for one release.
