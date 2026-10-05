# BUG-150 — A Market tab closed while its first window loads reports on its deleted chart

- **Reported:** 2026-10-05 (another session's independent review of the EPIC-033 work, noted as pre-existing in `support/charting`; reproduced here)
- **Severity:** 🟢 P3 — when a chart tab is closed during its sync, the window log gets a spurious "System error: Signal source has been deleted" line, and an unhandled `RuntimeError` reaches the thread pool. Nothing is drawn wrong and no order is affected.
- **Status:** ✅ Fixed (2026-10-05)
- **Context:** [SPEC-002](../../../Docs/SPEC/SPEC-002_watch_the_live_market.md) (watch the live market) → `src/support/charting/live_chart/` (shared by the Market, desk and bot charts) → UI support / worker seam
- **Environment:** Linux, offscreen Qt, `master-warrior` at `4a7f0b7`.

## Reproduction
1. Open the Market mode live, then open a symbol (here ETHUSDT). Its first window is submitted to the thread pool.
2. Close the tab before the worker runs. `MarketPresenter._close_chart` calls `shutdown()` and `release_stream()`, then `deleteLater()`.
3. Let the deferred delete run, then the worker.

- **Expected:** the closed tab says nothing.
- **Actual:** `RuntimeError: Signal source has been deleted`. It is raised at `live_chart_coordinator.py` `_run` (the first `log` callback), again from the `except` branch's `stream_failed`, and again from `finally`'s `load_finished`.
- **Frequency:** always, in this order.

## Symptom
```
src/support/charting/live_chart/live_chart_coordinator.py:106: RuntimeError
>           self._callbacks.stream_failed(f"System error: {exc}")
E   RuntimeError: Signal source has been deleted
src/support/charting/live_chart/live_candle_chart.py:68: RuntimeError
```

## Root cause
- **The emitting object:** every `LiveChartCallbacks` member is bound to a signal of the owning `LiveCandleChart` (`live_candle_chart.py:61-72`).
- **The unchecked path:** `LiveChartCoordinator._run` checked the cancellation token only between steps, not before each report:
  - it logged before its first check;
  - it reported failures from the `except` branch;
  - it called `load_finished()` unconditionally in `finally`.
- **The trigger:** `LiveCandleChart.shutdown()` cancels the token, but a Market tab's chart is then `deleteLater`'d. A worker that runs afterwards emits on a deleted `QObject`.
- **Why the gate missed it:** `MarketChart`'s own loads (`EPIC-033S`) had already been fenced this way (`market_chart.py` `_read_stored`); the coordinator beneath every chart had not.
- **Why `load_finished` needed more than a token check:** it could not simply be silenced, because `MarketChart` counts first windows by their settles ("exactly once per request").

## Fix
- **`live_chart_coordinator.py`:** a per-load `_Reporter` calls each callback only while the load's token is not cancelled. A cancelled load reports nothing, `load_finished` included, and `load_finished` now carries the load's token.
- **`live_chart_callbacks.py`:** `load_finished: Callable[[CancellationToken], None]`.
- **`live_candle_chart.py`:**
  - `_restart` settles the request it cancels itself, on the Qt thread, so "once per request" still holds.
  - `_load_settled` carries the token. `_on_load_settled` ignores a settle whose request was already replaced: one that was on its way when the restart happened.
- **Scope:** the repair is at the seam all three charts share (Market, desk, bot), not in the Market presenter.
- **`cancellable_report.py`** (added after the review of PR #370): `report_unless_cancelled(token, emit, *args)` is the one place a worker reports to a chart.
  - **The gap it closes:** the token check alone left a window between the check and the emit, in which the Qt thread can cancel and delete the chart.
  - **How:** a `RuntimeError` from the emit is dropped only when the token is cancelled by then, which proves that race. Any other `RuntimeError` still raises.
  - **Callers:** both `_Reporter` and `MarketChart._read_stored` (the EPIC-033S loads, the same family) use it.

## Regression test
- **`tests/unit/modules/trading/ui/market/test_market_chart_cancelled_load.py::test_a_tab_closed_while_its_first_window_loads_reports_nothing`:**
  - before the fix it failed with the `RuntimeError` above, through the real presenter, chart and coordinator;
  - it passes after the fix.
- **Same file, `test_a_replaced_loads_settle_does_not_end_the_new_ones_loading`:** a settle of a replaced request leaves the new one loading. It goes red when the token match is removed.
- **`tests/unit/support/charting/live_chart/test_live_chart_coordinator.py`:**
  - `test_a_cancelled_load_reports_nothing` goes red when the reporter's gate is removed;
  - `test_a_settled_load_names_its_own_token`.
- **`tests/unit/support/charting/live_chart/test_cancellable_report.py`:** a chart closed between the check and the emit is dropped, and an unexplained `RuntimeError` still raises. Each of these turns a test red: always re-raising, or never re-raising.
- **Mutation:** removing `_restart`'s own settle turns 3 Market tests red (the commands stay off forever).

## Verification
- Run: `tests/unit/modules/trading/ui`, `tests/unit/support/charting` and `tests/unit/modules/bots`, all green, plus the commit tier (`ci-local.ps1 -SkipTests`). Results are in PR #370.
- **Positive proof:** the reproduction above now runs to the end with the closed tab's chart gone, and its log holds no ETHUSDT line.
