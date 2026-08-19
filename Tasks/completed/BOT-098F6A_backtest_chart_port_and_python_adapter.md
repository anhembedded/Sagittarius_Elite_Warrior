# BOT-098F6A — Backtest chart port and Python adapter

**Parent:** [`BOT-098F6`](../completed/BOT-098F6_backtest_chart_host_migration.md)  
**Depends on:** `BOT-098F5` ✅  
**Priority:** P1  
**Complexity:** M  
**Status:** Completed

## Result

`src/presentation/ui/screens/backtest/logic/backtest_chart_host.py` adds
`IBacktestChartHost` (Protocol), `PythonBacktestChartHost` (pure delegation
wrapper around `ChartCard`) and `BacktestChartHostFactory` (transient,
view-owned). `BackTestView.render_symbol_cards()` now builds hosts through
the factory instead of constructing `ChartCard` directly, and
`BackTestPresenter`'s two direct `.toolbar` touches go through
`connect_timeframe_changed()`/`set_active_timeframe()` instead. Every other
call site in the View/Presenter needed no change — they already called
methods like `render_historical_data()`/`set_chart_type()`/
`add_overlay_indicator()` on whatever object `chart_cards[0]` held, so the
same duck-typed calls now land on the host instead of the raw card.

Existing tests that reached into `ChartCard`-internal state (`fps_overlay`,
`plot_layout`, `toolbar._buttons`, `_raw_history`, `chart_type_renderer`,
`indicators`) migrated to a `PythonBacktestChartHost.chart_card` escape
hatch — an explicit "tests may still reach the concrete Python renderer's
internals; production code must not" boundary, since a future native host
won't have those attributes at all. New tests in
`tests/unit/presentation/ui/screens/test_backtest_chart_host.py` cover
delegation of every port method, distinct-instance-per-factory-call, and
deterministic cleanup of the previous host's `ChartCard` on
`render_symbol_cards()` replacement. 243 Backtest-scoped tests and
`./scripts/ci-local.ps1 -Full` pass.

## Goal

Create a narrow Backtest-only chart host protocol, transient factory and Python
adapter around the existing `ChartCard`, without changing renderer, data,
interaction or visible behavior. This is the seam that lets future native work
be added without the Presenter/View knowing a concrete chart implementation.

## Scope

- Define only Backtest-used operations: widget/header attachment, timeframe
  toolbar signal/state, historical OHLC/volume, overlay/subplot indicators,
  script artifacts, trade markers, display timezone, chart mode, visibility
  toggles, dev diagnostics and cleanup.
- Move BackTestView/Presenter from direct `ChartCard` / `.toolbar` access to
  the host port and make the factory transient/view-owned.
- The only implementation in this phase is Python `ChartCard` delegation;
  native runtime, QML, config and C++ are excluded.

## Acceptance criteria

1. Existing Backtest unit/integration behavior is unchanged using the Python
   adapter: timeframe, OHLC/Equity/BOTH modes, strategy/script indicators,
   volume, markers and timezone all retain their current output.
2. Production Backtest View/Presenter import the port/factory only; no direct
   `ChartCard` references remain outside the Python adapter/factory.
3. A unit test demonstrates a distinct adapter instance per BackTestView and
   deterministic cleanup on `render_symbol_cards()` replacement.
4. Existing integration tests no longer assert private `ChartCard` state; they
   assert the Backtest host contract/visible data instead.
5. Focused tests and `./scripts/ci-local.ps1 -Full` pass.
