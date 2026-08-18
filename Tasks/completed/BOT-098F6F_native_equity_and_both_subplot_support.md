# BOT-098F6F — Native Equity/BOTH Subplot Support

**Parent:** [`BOT-098F6`](BOT-098F6_backtest_chart_host_migration.md)  
**Depends on:** `BOT-098F6D` ✅  
**Priority:** P2  
**Complexity:** L  
**Status:** Completed ✅  

## Goal

Extend the native Backtest chart host to cover `ChartDisplayMode.EQUITY` and `ChartDisplayMode.BOTH`, eliminating the Python-fallback restriction for these modes. The C++ Native Chart now seamlessly handles 100% of Backtest chart modes.

## Work Accomplished

1. **`NativeBacktestChartHostAdapter` (`src/presentation/ui/screens/backtest/logic/native_backtest_chart_host_adapter.py`)**:
   - Added support for `line` chart type alongside `candlestick` (`_SUPPORTED_CHART_TYPES = frozenset({"candlestick", "line"})`).
   - Line chart rendering flushes pending synthetic OHLC candles directly to `submit_ohlcv` with empty volume.
   - `add_subplot_indicator` registers and renders equity/subplot indicator line via native indicator series.
   - Implemented dynamic per-indicator visibility toggling (`set_indicator_visible`) natively without falling back to Python.

2. **`BackTestView` (`src/presentation/ui/screens/backtest/backtest_view.py`)**:
   - Updated `_effective_chart_backend()` to return `_chart_backend` for all modes (`OHLC`, `EQUITY`, `BOTH`), removing the forced Python restriction.
   - Retained the native chart host across mode switches without unnecessary widget reconstruction.

3. **Comprehensive Test Verification**:
   - Added unit tests in `tests/unit/presentation/ui/screens/test_native_backtest_chart_host_adapter.py` verifying line chart type, subplot indicator registration, and visibility toggling.
   - Updated `tests/unit/presentation/ui/screens/test_backtest_chart_host.py` and `test_backtest_presenter.py` to assert that `EQUITY` and `BOTH` modes use native host when configured.
   - Validated against `./scripts/ci-local.ps1 -Full` (1,143 unit/integration tests, 37 sanity tests, 94.20% coverage, 100% passed).
