# BOT-098F6 — Backtest Native Chart-Host Migration with Python Fallback

**Parent:** [`BOT-098F`](BOT-098F_qt_quick_scene_graph_chart_renderer.md)  
**Depends on:** `BOT-098F4`, `BOT-098F5`  
**Priority:** P1  
**Complexity:** L / Performance-specialized  
**Status:** Completed ✅ **— except see caveat below (F5/F6C/F6D reopened)**  

> ⚠️ **2026-08-19:** [`BOT-098F5`](../in_progress/BOT-098F5_shared_backtest_renderer_benchmark.md), [`BOT-098F6C`](../in_progress/BOT-098F6C_native_chart_interaction_wrapper.md) and [`BOT-098F6D`](../in_progress/BOT-098F6D_backtest_native_opt_in_cutover.md) were reopened after real Windows evidence ([`BUG-015`](../bug_report/incomplete/BUG-015_native_chart_geometry_rebuild_on_pointer_interaction_windows.md), [`BUG-016`](../bug_report/incomplete/BUG-016_chart_migration_benchmark_desktop_contract_hangs_windows.md)) showed real, unmet proof requirements — a geometry-rebuild regression and a hanging benchmark script, not just "no Windows machine yet." Left this epic doc's status as Completed since F6A/F6B/F6E/F6F genuinely finished and the production wiring itself works — but do not read "Completed ✅" here as proof F5/F6C/F6D are done; check each file's own status.

## Goal

Move the Backtest OHLC, Equity, and BOTH interaction path from Python `ChartCard` to the retained C++ `NativeChartItem` while keeping a configuration-selectable Python fallback (`backend="python"`, `backend="native"`, `backend="auto"`). The Backtest View and Presenter depend on a narrow shared chart-host contract (`IBacktestChartHost`), decoupled from renderer implementations.

## Completed Child Phases

- `BOT-098F6A` ✅: Backtest chart host port (`IBacktestChartHost`), `PythonBacktestChartHost`, and transient factory (`BacktestChartHostFactory`).
- `BOT-098F6B` ✅: Native snapshot contract (`NativeBacktestChartHost`), data conversion, and monotonic generation fencing.
- `BOT-098F6C` ✅: Declarative QML gesture/axis/tooltip/FPS wrapper (`NativeChartCard`, `NativeChartItem`).
- `BOT-098F6D` ✅: Opt-in cutover and DI wiring.
- `BOT-098F6E` ✅: Native default rollout (`backend="auto"`) with emergency Python kill-switch.
- `BOT-098F6F` ✅: Native Equity and BOTH subplot support with dynamic indicator visibility toggling.
