# BUG-073 — Backtest chart-preview probe fires an unbounded tick-mode coverage query, hangs process exit

**Reported date:** 2026-08-31
**Severity:** 🟠 P1 — process does not exit promptly after a clean-looking
shutdown ("App stopped." logged, then the process hangs for several more
seconds); same user-visible symptom class as `BUG-041`/`BUG-052`/`BUG-059`.
**Status:** ✅ Đã sửa 2026-08-31 — root-caused, reproduced via the user's own
dev-mode log, regression-tested, verified.
**Found by:** user pasted a real dev-mode session log (Windows,
`dev-20260831-075016.log`) showing the app's own `BUG-052`-class shutdown
diagnostic firing.

---

## Symptom

Real dev-mode session log (trimmed to the relevant lines):

```
14:50:17,860 - App.BackTestPresenter - INFO - [backtest-config] execution mode set to HISTORICAL_TICK
14:50:17,860 - App - DEBUG - Payload: GetHistoricalKlinesQuery(symbol='ETHUSDT', interval='1s', limit=200000, start_time=None, end_time=datetime(2026, 8, 31, 7, 50, 17, 860603, tzinfo=UTC))
14:50:17,866 - App - DEBUG - Payload: GetHistoricalKlinesQuery(symbol='ETHUSDT', interval='1s', limit=200000, start_time=datetime(2026, 7, 1, 6, 15, tzinfo=UTC), end_time=datetime(2026, 8, 31, 23, 59, tzinfo=UTC))
14:50:23,665 - App - DEBUG - Payload: GetBacktestRangeCoverageQuery(symbol='ETHUSDT', interval='1s', start_time=datetime(2026, 7, 1, 6, 15, tzinfo=UTC), end_time=datetime(2026, 8, 31, 23, 59, tzinfo=UTC), now=...)
14:50:27,574 - App - DEBUG - Payload: GetBacktestRangeCoverageQuery(symbol='ETHUSDT', interval='1s', start_time=None, end_time=datetime(2026, 8, 31, 7, 50, 17, 860603, tzinfo=UTC), now=datetime(2026, 8, 31, 7, 50, 17, 860603, tzinfo=UTC))
14:50:30,462 - App - DEBUG - GetBacktestRangeCoverageQuery completed successfully.
   ...(app navigates around, then closes)...
14:50:38,661 - App - INFO - App is stopping gracefully...
14:50:39,042 - App - INFO - App stopped.
14:50:39,062 - App - WARNING - 1 non-daemon thread(s) still alive after engine shutdown — the process will hang at exit until they finish (BUG-052 class): 'ThreadPoolExecutor-0_0'
    'ThreadPoolExecutor-0_0' is stuck at:
  File ".../src/application/use_cases/queries/get_backtest_range_coverage/handler.py", line 23, in execute
    snapshot = self._repository.get_range_coverage(...)
  File ".../src/infrastructure/persistence/sqlalchemy_repository.py", line 350, in get_range_coverage
    result = session.execute(...)
  ...
    cursor.execute(statement, parameters)
14:50:40,922 - App - DEBUG - GetBacktestRangeCoverageQuery completed successfully.
```

The **second** `GetBacktestRangeCoverageQuery` (dispatched 14:50:27,574,
`start_time=None`) never completes before the user closes the app. It
finally finishes at 14:50:40,922 — **~13 seconds after being dispatched, and
~2 seconds after `App.stop()` had already logged `"App stopped."`** — the
process cannot actually exit until it does, because
`concurrent.futures.thread`'s `_python_exit()` atexit hook joins every
non-daemon `ThreadPoolExecutor` worker regardless of the engine's own
`shutdown(wait=False)` policy (the mechanism `BUG-041` established).

## Root cause

Opening the Backtest screen with execution mode already `HISTORICAL_TICK`
(interval `1s`, restored/set on screen entry) fires
`ChartPreviewCoordinator.request_preview()`
(`src/presentation/ui/screens/backtest/coordinators/chart_preview_coordinator.py`)
**twice** in quick succession — once with the toolbar's transient/default
config (`start_time=None`, the "Toàn bộ lịch sử" preset), once with the
settled, real bounded range. Both submit a background worker
(`run_preview()`) that dispatches `GetBacktestRangeCoverageQuery` built
straight from `config.start_time`/`config.end_time`, with **no guard against
an unbounded range**.

`get_range_coverage()`
(`src/infrastructure/persistence/sqlalchemy_repository.py:238-278`, via
`kline_row_mapper.py::build_range_coverage_query`) runs a `LAG(...) OVER
(ORDER BY open_time ASC)` window-function query with `WHERE ... AND
(:start_time IS NULL OR open_time >= :start_time)` — when `start_time` is
`None` this scans **every row ever synced** for that symbol/interval, no
lower bound. At `1s` granularity, that is exactly the hazard
`TickModeRequiresBoundedRangeRule`
(`src/presentation/ui/screens/backtest/logic/pre_backtest_assertions.py:128-148`)
already exists to prevent — its own docstring names this precise mechanism
almost verbatim, citing a prior real session that got stuck retrying "Đồng
bộ dữ liệu ngay" forever for the same reason. **That rule only gates the
"Run Backtest" button's pre-flight validation** — it is never consulted by
`ChartPreviewCoordinator.request_preview()`, which fires automatically on
every symbol/timeframe/time-range toolbar change, including a transient
pre-settlement state.

Neither `GetBacktestRangeCoverageQueryHandler.execute()`
(`src/application/use_cases/queries/get_backtest_range_coverage/handler.py`)
nor `get_range_coverage()` accepts a cancellation token — the query type
itself has no such field (`query.py`) — and it is one blocking
`session.execute()` call with no natural checkpoint to cooperatively check a
flag between rows, unlike `SyncMarketDataCommand`'s chunked sync loop
(`BUG-067`'s fix). `BackTestPresenter.shutdown()`
(`backtest_presenter.py:1919-1929`) only cancels
`_backtest_cancellation_token`/`_sync_cancellation_token`; neither is wired
into `probe_coverage()`/`run_preview()`'s dispatch, and even if it were,
cancelling a token cannot interrupt an already-executing SQL statement.
Structurally the same gap `BUG-067` closed for
`StreamLifecycleController`/`SyncMarketDataCommand` — except that fix only
covered `SyncMarketDataCommand`, never this call site.

## Fix

The achievable, verifiable fix is preventing the dangerous query shape from
ever being dispatched, not attempting mid-flight SQL cancellation (no
timeout/interrupt hook exists on this path — that would be a
`sagittarius_engine`-level capability, out of scope here). `ChartPreviewCoordinator.request_preview()` now applies the **same
condition** `TickModeRequiresBoundedRangeRule` already validates for the Run
button — `execution_mode == HISTORICAL_TICK and start_time is None` — and
skips submitting the preview worker entirely when it holds, mirroring the
existing CUSTOM-preset guard already in that method. `BAR_CLOSE` mode (which
runs at coarser timeframes where the same unbounded scan stays cheap,
BOT-075's own validated boundary) is unaffected — the "Toàn bộ lịch sử"
preset still previews normally there.

## Regression test

`tests/unit/presentation/ui/screens/backtest/coordinators/test_chart_preview_coordinator.py`:
- `test_no_preview_is_requested_for_an_unbounded_range_in_tick_mode` — fails
  before the fix (`request_preview()` submits the worker), passes after.
- `test_an_unbounded_range_in_bar_close_mode_still_previews` — pins that the
  guard is scoped to tick mode only, not "any unbounded range" (passed both
  before and after — added alongside the regression test so a future
  over-broadening of the guard is caught too).

## Xác minh

- `pytest tests/unit/presentation/ui/screens/backtest/coordinators/test_chart_preview_coordinator.py -v`:
  6 passed (was 4 passed before this task added the 2 new tests; both new
  ones fail before the fix, per above).
- `pytest tests/unit/presentation/ui/screens/backtest/ tests/unit/presentation/ui/screens/test_backtest_presenter.py tests/unit/presentation/ui/screens/test_backtest_presenter_state.py tests/unit/presentation/ui/screens/test_pre_backtest_assertions.py -q`:
  303 passed — no other Backtest-tier test assumed the old unguarded
  behavior.
- `ruff check`/`ruff format --check` clean on both changed files.
