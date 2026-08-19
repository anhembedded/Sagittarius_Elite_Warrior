# BOT-098F6D — Backtest native opt-in cutover

**Parent:** [`BOT-098F6`](../completed/BOT-098F6_backtest_chart_host_migration.md)  
**Depends on:** `BOT-098F5`, `BOT-098F6A` ✅, `BOT-098F6C`  
**Priority:** P1  
**Complexity:** L  
**Status:** In Progress

> 🔁 **Reopened 2026-08-19.** This file was moved into `completed/` by an earlier session, but its own `Status:` line here was never changed to `Completed` — a real inconsistency between file location and documented state, not a deliberate sign-off. Investigating why turned up a concrete, unresolved reason this task's own stated proof requirement is not met: acceptance criterion 5 ("`BOT-098F5` DPR 1 and DPR 2 reports are published against the production host wiring") depends on `BOT-098F5`, which is itself reopened for the same reason ([`BUG-016`](../bug_report/BUG-016_chart_migration_benchmark_desktop_contract_hangs_windows.md) — the exact script that would produce those reports hangs indefinitely on Windows). This file's own "Not yet done" section already named the missing Windows RHI evidence; that gap is now attached to a specific, open bug rather than a generic "no Windows machine" excuse. Do not re-close without `BOT-098F5` closing first.


## Goal

Wire the factory into the production Backtest route so a configuration-selected
native OHLC path can render real Backtest data, with explicit capability
fallback to the existing Python renderer for modes not yet native-supported.

## Scope

Allowed native scope in this slice:

- OHLC candles, volume bars, price-overlay indicators, truthful LONG entry/exit
  markers, pan/zoom, crosshair/tooltip, timezone-aware axes and dev FPS.
  They must be driven by a stable config selection and action-aware
  diagnostics.

Outside native scope in this slice (must retain Python explicitly):

- equity-only and BOTH subplot, line/area/Heikin-Ashi implementations in C++,
  script regions, script info and arbitrary script marker text. Unsupported
  presentation modes must select the Python host with one explicit testable
  transition rule; no silent visual omission.

This slice also owns the user-facing contract: config layering, env source
followed by app/user JSON sources, `backtest.chart.backend =
python|native|auto` enum/default, fallback selection, backend-switched teardown
and integration coverage.

## Acceptance criteria

1. DI registers the factory only; no QWidget/QQuickWidget is singleton.
2. Each BackTestView construction selects host via the stable config hierarchy;
   selection is once per view construction and requires view reconstruction on
   backend change.
3. Missing plugin, ABI mismatch, construction or post-construction viewport,
   snapshot or QML failure returns the Python fallback once with one actionable
   log and zero blank chart.
4. OHLC backtest and preview data reach the rendered host; unsupported modes
   newly take the Python fallback deterministically; one valid Backtest probe
   path exits zero before the benchmark.
5. `BOT-098F5` DPR 1 and DPR 2 reports are published against the production host
   wiring; native must not lose the coverable host integration tests.
6. Unit, Backtest integration, sanity/layout and probe tests, plus
   `./scripts/ci-local.ps1 -Full`, pass.

## Result

`BacktestChartHostFactory.create()` now takes `backend: "python"|"native"|"auto"`
(`SAGITTARIUS_BACKTEST_CHART_BACKEND` env var → `backtest.chart.backend` config
→ `"python"` default). `"native"`/`"auto"` try `NativeBacktestChartHost.create()`
first; a missing plugin, ABI mismatch or construction failure logs one warning
and falls back to `PythonBacktestChartHost`, never a blank chart. The new
`NativeBacktestChartHostAdapter` (`native_backtest_chart_host_adapter.py`)
bridges `NativeBacktestChartHost` behind `IBacktestChartHost`: OHLC candles +
volume + overlay indicators + truthful LONG/SHORT markers + timezone + dev FPS
go through; equity/BOTH subplot, non-candlestick chart types, script
regions/info and non-trade marker keys raise `NativeUnsupportedFeatureError`,
which `BackTestPresenter` catches and turns into a Python rebuild via
`_fallback_to_python_after_unsupported_native_feature()` — wired at every
call site that can reach the native host: script region/info/marker (already
existing), and, added in this pass after a real gap was found, the two
OHLCV/preview data paths (`_on_chart_data_ready`, `_on_preview_data_ready`).
`BackTestView` rebuilds the host on any mode change that alters the effective
backend (native supports OHLC only) and exposes `refresh_chart()` as the
public re-render entry point for these mid-session rebuilds.
`BacktestChartHostFactory` is bound transient (`container.bind`, never
singleton) in `binance_bot_module.py`.

**A real bug was found and fixed while testing the new OHLCV-rejection
fallback, not just written and assumed correct:** `BackTestView._render_chart()`
unconditionally read `self._last_result.trades` when the trade-flags toggle
was checked, but `refresh_chart()` (this task's own new public entry point)
can run it while still in preview state, where `_last_result` is `None` —
an `AttributeError` crash. Fixed by gating that branch on
`self._last_result is not None`, matching what `on_preview_data_ready()`
already does directly. Caught by a new regression test
(`test_preview_data_ready_falls_back_to_python_when_native_rejects_the_snapshot`)
that failed before the fix and passes after it.

Verified for real, not just written:
- 121 `test_backtest_presenter.py` tests, including the OHLCV/preview
  fallback pair (acceptance criterion 3) and the chart-mode-rebuild stale-
  bookkeeping regression above.
- 17 `test_native_backtest_chart_host_adapter.py` tests (adapter port-bridging
  logic, `NativeBacktestChartHost` mocked).
- 16 `test_backtest_chart_host.py` tests, including backend selection,
  env-override priority, and mode-change rebuild/no-rebuild behavior.
- 301 Backtest-scoped tests and 37 `tests/sanity/` tests (including the new
  themed-background regression above), all passing.
- New sanity test `test_backtest_native_chart_di_sanity.py`: boots the real
  app, sets `backtest.chart.backend=native` through the real `ConfigManager`
  (not env override, not a mocked container), constructs the real
  `BackTestPresenter` against the real DI container, and asserts
  `view.chart_cards[0]` is the real `NativeBacktestChartHostAdapter` — closes
  the gap the unit tests (mocked container) structurally cannot cover.
- **Desktop E2E, the piece BOT-098F6C explicitly left as this task's
  responsibility, is now real evidence, not a component probe:** new
  `scripts/native_backtest_desktop_e2e.py` drives the actual app entry-point
  components (`QApplication`, `configure_app_qml`, `MainWindow` — the same
  ones `app_bootstrapper.main()` assembles) on this machine's real Wayland
  session (`DISPLAY`/`WAYLAND_DISPLAY`, refuses to run under
  `QT_QPA_PLATFORM=offscreen`), switches to the real Backtest screen,
  confirms the real, DI-resolved chart host is `NativeBacktestChartHostAdapter`
  (not a mock), feeds it real OHLC preview data through the exact
  `BackTestView.on_preview_data_ready()` call `BackTestPresenter` itself uses,
  and drives real wheel-zoom and drag-pan `QTest` mouse input against the
  actual embedded widget (BOT-098F6C already proved hover-only crosshair
  input is flaky on this machine's virtual Wayland session specifically, so
  only the two input types proven reliable there are asserted). Captured zero
  Qt warnings/errors across two independent runs, both exiting 0.
- `./scripts/ci-local.ps1 -Full` passes end to end: Native Chart Build, Chart
  Benchmark Contract, Ruff Lint, Ruff Format, 1112 primary tests (coverage
  93.51%, threshold 80%), and 36 sequential Sanity tests.

**Two more real bugs were found and fixed after real interactive usage
(`run-ui.ps1`), not just automated evidence — both confirmed unrelated to
this task's own scope, but both directly caused by this task's own wiring
making native reachable from the real app for the first time:**

1. **Blank white chart background.** Reported by the user running the real
   app with native active: the Backtest chart area showed pure white
   whenever no candle snapshot had reached the native host yet (sync still
   in progress/failed). Root cause: `NativeChartItem::updatePaintNode()`
   (`native/chart_renderer/native_chart_item.cpp`) only ever builds candle/
   volume/axis/marker geometry nodes — it never paints a background — and
   `NativeBacktestChart.qml`'s root `Item` had no `color` of its own either,
   so the widget fell through to `QQuickWidget`'s default white clear color.
   Regression test written first (`test_chart_has_a_themed_background_before_any_data_is_submitted`
   in `tests/sanity/test_native_backtest_chart_interaction_sanity.py`),
   confirmed failing for the right reason, then fixed by adding a themed
   `Rectangle` (`Theme.bgCard` / `#111318`, matching `#base_card`'s own QSS
   background) behind `NativeChartItem` in the QML wrapper.
   `scripts/native_backtest_desktop_e2e.py` was also strengthened at the
   same time to sample real composited pixels via `widget.grab()` — not just
   check "correct type constructed, zero Qt warnings," which structurally
   could never have caught a silent visual defect like this. Verified with
   real pixel colors on the real Wayland session across three independent
   runs: background samples `#111318` (never white) before data, and real
   candle-color pixels (`#00c087`) appear after data is submitted.
2. **Strategy/script indicator lines silently vanished after a chart-mode
   round-trip** (Nến Nhật → Đường Vốn → Nến Nhật) while native was active,
   and the very next EMA-visibility toggle crashed silently (swallowed by
   `safe_ui_action` outside dev mode). Root cause: `BackTestView.set_chart_mode()`
   rebuilds the chart host from scratch whenever the effective backend
   changes, but `BackTestPresenter` kept believing its old
   `_active_strategy_lines`/`IndicatorScriptRunner` bookkeeping still applied
   to the brand new, empty host — `card.set_indicator_visible(stale_name, ...)`
   then unconditionally raised `NativeUnsupportedFeatureError` on native.
   Fixed the minimal way (explicitly chosen over caching+replaying indicator
   data, to avoid adding more state to an already-complex path):
   `set_chart_mode()` now returns whether it actually rebuilt the host;
   `_on_chart_mode_changed()` uses that to drop the stale bookkeeping
   (`_active_strategy_lines.clear()` + new
   `IndicatorScriptRunner.reset_after_host_replaced()`, which deliberately
   does *not* call the existing `dispose_all()`/`clear_from_chart()` path
   since those dispose callables are bound to the already-replaced `ChartCard`
   and invoking them risks a "C++ object already deleted" crash for no
   benefit). Post-fix behavior: a mode round-trip cleanly loses indicator
   lines (same as it would have before this task even existed, since nothing
   ever rebuilt hosts before it) instead of leaving a silently-crashing stale
   reference — re-running the backtest redraws them from scratch either way.
   Regression test written first and confirmed failing for the right reason,
   then updated to assert the fixed behavior
   (`test_switching_chart_mode_away_and_back_clears_stale_indicator_bookkeeping`).

Two more, unrelated, pre-existing bugs were found by the user during the same
manual testing session and filed separately rather than fixed here, since
neither has anything to do with this task's scope (confirmed: both predate
`BOT-098F6A`, neither touches chart-host/native code):
[`BUG-009`](../bug_report/BUG-009_backtest_cached_frame_preview_widget_shift.md)
(Python-only cached-frame drag-preview widget positioning) and
[`BUG-010`](../bug_report/BUG-010_backtest_sync_never_satisfies_range_coverage.md)
(Backtest sync/coverage-check possible cutoff mismatch).

**Not yet done:** real-Windows RHI verification of this same cutover (this
machine is Linux) — none of this task's own six acceptance criteria name
Windows explicitly, unlike `F4`'s pixel-color criterion or `F5`'s benchmark
tier, so this is recorded as an open item rather than a blocker, matching
`BOT-098F6`'s parent scope. `BOT-098F5`'s DPR1/DPR2 benchmark reports
predate this task's production wiring; `ci-local.ps1 -Full`'s Chart
Benchmark Contract step re-validates both renderers against the current
tree on every run and passed here, but a fresh dedicated DPR1/DPR2 report
specifically against the production `BackTestPresenter` path (rather than
the standalone benchmark harness) has not been separately published.

Status kept as **In Progress** pending user review of this diff before
commit — the user asked for the implementation and tests to be finished
without a commit so they can review first.
