# BOT-098F5 — Shared Backtest renderer benchmark (Python vs native)

**Parent:** [`BOT-098F`](BOT-098F_qt_quick_scene_graph_chart_renderer.md)  
**Depends on:** `BOT-098F1` / `BOT-098F2` / `BOT-098F2A` / `BOT-098F3` ✅, `BOT-098F4`  
**Priority:** P1  
**Complexity:** L / Performance-specialized  
**Status:** In Progress

## Progress

Harness built and verified end-to-end on a local Linux dev machine (Qt 6.11.1
`linux_gcc_64` via `aqtinstall`, matching PySide6's ABI). Reference-machine
report published at
[`Tasks/reports/BOT-098F5_shared_renderer_benchmark.md`](../reports/BOT-098F5_shared_renderer_benchmark.md)
with real DPR 1 and DPR 2 `--backend both --ci-contract` runs: native is
50–129× faster than Python per camera update, crosshair candle truth holds,
OHLCV/volume/indicator geometry stays retained across camera and pointer
interaction (marker retained for pointer only, as the boundary contract
already documents), zero Qt warnings.

Still outstanding: acceptance criterion 6's **Windows Desktop E2E** tier —
real pixel-color evidence under a real GPU/RHI backend needs an actual
Windows machine and cannot be produced from this environment. Unit,
Integration and Sanity tiers are green.

## Goal

Create one reproducible, fair local benchmark that exercises the same Backtest
chart profile on both the current Python `ChartCard` and C++
`NativeChartItem`. It is the performance and visual evidence gate for the
native-production migration; it is **not** a hard timing gate for shared CI.

## Boundary contract

- The frozen payload is 6,420 ordered OHLCV candles, volume, five price-overlay
  indicators, 1,112 semantically distinct trade markers, and crosshair input.
  The measured viewport is 1,600×900 logical pixels with 150 visible candles.
- Both backends must use the same source fixture, warmup/measurement count,
  final viewport sequence, crosshair sequence and event draining. Native uses
  `QQuickView.grabWindow()`; the QWidget Python renderer uses its equivalent
  completed `QWidget.grab()` capture. Timing a setter alone is not evidence.
- This is a renderer-level A/B, not a claim that the production Backtest
  `QQuickWidget` host has the same number. `BOT-098F6D` must rerun the shared
  profile after production host wiring before native becomes default.
- Report median/p95 frame cost, updates/s, requested and actual backend,
  resolution, DPR, Qt/PySide/pyqtgraph/native runtime versions, marker
  display/represented counts, sampled visual colors and Qt warnings.
- The native path must prove that pointer/camera updates do not rebuild OHLCV,
  volume, indicator or marker geometry. The Python path reports its equivalent
  range/apply and visible-marker diagnostics.
- The benchmark may not hide markers, lower DPR, downsample business data or
  skip the final visual grab merely to improve a number.
- Desktop timing is Windows opt-in diagnostic evidence. Headless tests cover
  harness/fixture/report contracts only; `ci-local.ps1 -Full` never fails on
  a machine-dependent frame threshold.

## Implementation

1. Add a narrow, Backtest-only chart-host protocol and config-aware factory so
   the benchmark invokes each renderer through the same data/viewport contract.
   Do not turn the Dashboard `ChartCard` surface into a global abstraction.
2. Add `scripts/benchmarking/chart_migration_benchmark.py` with
   `--backend python|native|both`; reuse the canonical fixture and p95/report
   helpers from `backtest_chart_interaction.py` and `native_chart_*_probe.py`.
3. For each backend, render full payload, execute deterministic pan and
   crosshair bursts with `processEvents()` and `grabWindow()`, emit one
   normalized JSON result and a comparison/speedup result for `both`.
4. Add four-level proof: Unit tests for frozen fixture semantics, command
   selection, p95 calculation and normalized report fields; Integration through
   deterministic renderer adapters; Sanity for native runtime/QML construction;
   Windows Desktop E2E with real pan/wheel/pointer input, visual samples and Qt
   message capture. Preserve existing native QML visual probes as separate
   contracts.
5. Publish a reference-machine result in
   `Tasks/reports/BOT-098F5_shared_renderer_benchmark.md`, including DPR 1 and
   DPR 2 runs, command line, environment, visual/semantic checks and any
   warning output.

## Acceptance criteria

1. `--backend both` runs the same complete fixture through Python and C++ and
   produces self-describing JSON for both results plus speedup; no backend gets
   an easier workload.
2. Every measured update includes the real Qt completion path (`grabWindow()`),
   and output includes median, p95, updates/s and environment/DPR.
3. The C++ result asserts crosshair final candle truth and no increment to
   OHLCV/volume/indicator/marker geometry-build counters during camera/pointer
   interaction.
4. The report proves candle colors, entry/exit marker colors and indicator
   colors were visibly present and Qt warnings were empty.
5. Benchmark output is explicitly described as local diagnostic evidence, not
   a shared CI timing threshold.
6. Unit, Integration, Sanity and Windows Desktop E2E evidence each pass their
   own stated contract; focused tests and `./scripts/ci-local.ps1 -Full` pass.
