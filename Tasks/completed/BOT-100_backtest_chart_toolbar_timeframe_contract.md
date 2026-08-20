# BOT-100 — Backtest chart-toolbar timeframe data contract

**Source:** [`BUG-008`](../bug_report/completed/BUG-008_backtest_chart_toolbar_timeframe_noop.md)  
**Priority:** P1  
**Status:** Completed

## Goal

Make the visible timeframe controls embedded in the Backtest chart header
honest: selecting a timeframe must update the one Backtest configuration,
query the matching local history, and replace the rendered candles.

## Acceptance criteria

- Chart-header and QML timeframe picker stay synchronized through
  `BackTestViewModel.selectedTimeframe`.
- A chart-header click requests the same preview lifecycle as the QML picker.
- The user-visible chart receives candles whose cadence matches the selected
  timeframe; button highlighting alone is never accepted as proof.
- Keep unit, deterministic integration, construction sanity, and opt-in
  desktop E2E regressions permanently.
- Full local CI passes.

## Outcome

- `ChartToolbar.sig_timeframe_changed` is now owned by `BackTestPresenter` and
  updates the single `selectedTimeframe` source of truth.
- Both the QML picker and chart header stay synchronized; either route requests
  the same background preview lifecycle.
- The deterministic integration and desktop E2E prove a click on `5m` renders
  real 5-minute-spaced candles, rather than accepting a selected button style.
- Desktop E2E and Full CI passed: native CMake, Ruff, 1,029 primary tests, 28
  sanity tests, coverage 94.20%.
