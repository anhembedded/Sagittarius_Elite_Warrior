# Completed Task: BOT-085 / BUG-003 — Fix Volume Spike & Candle Overlap on Live Reload (and BUG-011 / BUG-012 Native Chart Fixes)

## 1. Summary of Work

### BOT-085 / BUG-003: Volume Bar Spike & Duplicate Candle Overlap on Live Reload
- **Root Cause**:
  - `VolumeItem.render_historical` reloads historical data up to timestamp `T` and resets `_live_index = None`.
  - When the next live tick arrives with timestamp `T`, `VolumeItem.update_live` previously appended a duplicate timestamp element `T` because `_live_index` was `None`.
  - At LOD levels $\ge 1$, `build_volume_lod_pyramid` paired the duplicate `T` elements together and summed their heights, causing a double-counted volume spike (`295.9036`).
  - Similarly, in `FastCandlestickItem`, `paint()` appended `live_candle` to `render_rows` without checking if the trailing historical candle had the same timestamp `T`, rendering two overlapping candlesticks with conflicting wicks at the same X position.
- **Fix**:
  - `VolumeItem.update_live`: checks if `_live_index` is `None` but `self._timestamps[-1] == timestamp` $\rightarrow$ sets `self._live_index = len(self._timestamps) - 1` and updates in-place (`append=False`).
  - `FastCandlestickItem.paint()` & `append_closed_candle`: updates in-place if the trailing candle has the same timestamp.
  - `ChartCard.append_closed_candle` & `DashboardPresenter._on_ui_chart_update`: guards trailing element deduplication.

### BUG-011 / BUG-012: Native Backtest Indicator Leading Gaps & Marker Alignment
- **Root Cause**:
  - `build_native_indicator_series`: when strategy indicators had warmup periods (e.g. EMA 20/26 having no values for initial bars), it raised `ValueError("indicator data has a leading gap with no prior value to hold")`.
  - `build_native_marker`: when Backtest ran on 50,000 candles with 957 trades and the chart loaded 5,000 candles, trades prior to the 5,000th candle raised `ValueError("marker timestamp does not align with any candle")`.
  - `remove_indicator`: `_resubmit_indicators()` called during `active.scope.dispose_all()` triggered the indicator crash, causing `ResourceScope teardown failed` during "Lưu & Re-Backtest" bot params save.
- **Fix**:
  - `build_native_indicator_series`: backfills leading warmup gaps with `first_known` and handles non-finite values cleanly without raising.
  - `submit_markers`: catches `ValueError` for out-of-window trade markers and skips them without aborting the render pass.
  - `_resubmit_indicators`: filters out series without valid data.

---

## 2. Verification

- Added unit regression tests in `tests/unit/presentation/ui/components/test_chart_card.py`:
  - `test_volume_live_update_after_historical_reload_does_not_duplicate_or_spike`
  - `test_candlestick_live_update_after_historical_reload_does_not_duplicate`
- Added unit regression tests in `tests/unit/presentation/ui/screens/test_native_backtest_chart_adapter.py`:
  - `test_backfills_a_leading_gap_from_the_first_sample`
  - `test_skips_non_finite_values`
  - `test_skips_unaligned_indicator_timestamps`
  - `test_submit_markers_skips_out_of_range_markers_without_error`
  - `test_submit_indicators_with_empty_or_warmup_series_succeeds`
- Full CI Verification (`.\scripts\ci-local.ps1 -Full`):
  - Native Chart build: passed
  - Benchmark contract: passed
  - Ruff Lint & Format: passed
  - Primary Tests: 1,122 passed, 94.23% coverage
  - Sanity Tests: 37 passed
  - Exit Code: 0
