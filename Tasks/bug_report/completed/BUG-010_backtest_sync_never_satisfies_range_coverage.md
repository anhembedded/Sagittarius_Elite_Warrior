# BUG-010 — "Đồng bộ dữ liệu ngay" never satisfies Backtest range coverage, no matter how many times it's clicked

**Reported:** 2026-08-18
**Severity:** P1 — user-visible, blocks running a Backtest at all in this state
**Reported:** 2026-08-18  
**Severity:** P1 — user-visible, blocks running a Backtest at all in this state  
**Status:** Resolved (2026-08-18)

## Root Cause Analysis

1. **SQLite Aggregation Query Cutoff**: In `SQLAlchemyMarketDataRepository.get_range_coverage()`, the query filtered by `open_time < :end_time` using raw `:end_time = now`.
2. When syncing market data from Binance, the currently forming candle (e.g. `open_time = 10:41:00`, `close_time = 10:41:59.999`) has `open_time < now` (e.g. `10:41:35`), and was included in the `ordered_klines` subquery in SQLite.
3. The SQL aggregation returned `last_record = 10:41:00` and `unclosed_candles = 1` (`close_time > now`).
4. However, `build_backtest_range_coverage()` computed `closed_end = floor_open_time(now, interval_seconds) = 10:41:00`, which expected the last closed candle to be `expected_last = closed_end - 60s = 10:40:00` and `unclosed_candles == 0`.
5. Because SQLite returned `last_record = 10:41:00` (which did not equal `10:40:00`) and `unclosed_candles = 1 != 0`, `is_fully_covered` was ALWAYS evaluated as `False`, prompting the user to sync indefinitely.

## Solution Implemented

1. **Aligned Query Scoping**:
   - In `SQLAlchemyMarketDataRepository.get_range_coverage()`, computed `closed_end = floor_open_time(min(as_utc(end_time), as_utc(now)), interval_seconds)` and `aligned_start = ceil_open_time(as_utc(start_time), interval_seconds) if start_time is not None else None`.
   - Filtered SQLite klines strictly with `open_time < :closed_end` and `(:start_time IS NULL OR open_time >= :start_time)`.
   - Exported `as_utc`, `floor_open_time`, and `ceil_open_time` from `src/application/services/backtest_range_coverage.py`.
2. **Defensive Native Chart & Timezone Error Barriers**:
   - Guarded `NativeChartItem::applyViewport` and `NativeChartItem::rebuildAxisTicks` against empty candle snapshots (`candleCount == 0U`), preventing unsigned underflow and out-of-bounds vector indexing.
   - Added defensive exception barriers in `NativeChartTimezoneBridge` and `display_timezone_service` to catch `(OSError, ValueError, OverflowError)` on invalid timestamp formats.
   - Filtered known benign Qt font warnings (`QFontDatabase: Cannot find font directory`) in `chart_migration_benchmark.py`.

## Verification & Test Evidence

1. **Reproducing Regression Test**:
   - `tests/integration/infrastructure/persistence/test_bug010_sync_range_coverage_regression.py` (5 closed candles + 1 forming candle verified to report `is_fully_covered == True` and `actual_candles == 5`).
2. **Sanity Suite**:
   - `.\scripts\ci-local.ps1 -SanityOnly` — 37 / 37 passed.
3. **Full CI Suite**:
   - `.\scripts\ci-local.ps1 -Full` — 100% clean (Native Build, Benchmark Contract, Ruff Lint, Ruff Format, 1,115 Unit/Integration tests with 93.53% coverage, 37 Sanity tests).

