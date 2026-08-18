# BOT-098F6A — Backtest chart port and Python adapter

**Parent:** [`BOT-098F6`](../backlog/BOT-098F6_backtest_chart_host_migration.md)  
**Depends on:** `BOT-098F5` ✅  
**Priority:** P1  
**Complexity:** M  
**Status:** In Progress

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
