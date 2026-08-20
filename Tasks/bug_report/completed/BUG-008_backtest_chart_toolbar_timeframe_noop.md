# BUG-008 — Backtest chart-header timeframe buttons were visual-only

**Reported:** 2026-08-17  
**Severity:** P1 — user-visible Backtest configuration/data contract  
**Status:** Fixed and verified

## Symptom

The visible `1m` / `5m` / `15m` / `1h` / `1d` buttons in the Backtest chart
header changed their selected styling, but the chart kept displaying the old
candles.

## Root cause

`ChartCard` correctly emitted `ChartToolbar.sig_timeframe_changed`, but
`BackTestPresenter._connect_chart_controls()` subscribed only chart modes and
overlay toggles. No subscriber updated `BackTestViewModel.selectedTimeframe`,
so no preview query or chart re-render could occur.

The old component test asserted only signal emission and highlighted styling:
an implementation contract, not the user-facing data contract.

## Permanent regression coverage

1. Unit: actual chart-toolbar button click updates the ViewModel and submits a
   5m preview snapshot; QML picker changes mirror back into the chart header.
2. Integration: real Backtest Presenter + local repository with separate 1h
   and 5m data receives a real Qt click and renders 5m-spaced candles.
3. Sanity: real DI/QML construction confirms the Backtest chart toolbar is
   composed with the supported quick timeframe controls.
4. Desktop E2E opt-in: `scripts/backtest_timeframe_toolbar_e2e.py` starts the
   real MainWindow, injects deterministic data, uses `QTest.mouseClick`, waits
   for `chartPreviewRendered`, verifies 5m chart data, and rejects Qt warnings.

**Verification:** Desktop E2E passed on Windows. Full CI passed: native CMake,
Ruff, 1,029 primary tests, 28 sanity tests, 94.20% coverage.
