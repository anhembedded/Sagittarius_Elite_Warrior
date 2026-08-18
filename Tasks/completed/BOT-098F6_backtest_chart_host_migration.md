# BOT-098F6 — Backtest Native Chart-Host Migration with Python Fallback

**Parent:** [`BOT-098F`](BOT-098F_qt_quick_scene_graph_chart_renderer.md)  
**Depends on:** `BOT-098F4`, `BOT-098F5`  
**Priority:** P1  
**Complexity:** L / Performance-specialized  
**Status:** Completed ✅  

## Goal

Move the Backtest OHLC, Equity, and BOTH interaction path from Python `ChartCard` to the retained C++ `NativeChartItem` while keeping a configuration-selectable Python fallback (`backend="python"`, `backend="native"`, `backend="auto"`). The Backtest View and Presenter depend on a narrow shared chart-host contract (`IBacktestChartHost`), decoupled from renderer implementations.

## Completed Child Phases

- `BOT-098F6A` ✅: Backtest chart host port (`IBacktestChartHost`), `PythonBacktestChartHost`, and transient factory (`BacktestChartHostFactory`).
- `BOT-098F6B` ✅: Native snapshot contract (`NativeBacktestChartHost`), data conversion, and monotonic generation fencing.
- `BOT-098F6C` ✅: Declarative QML gesture/axis/tooltip/FPS wrapper (`NativeChartCard`, `NativeChartItem`).
- `BOT-098F6D` ✅: Opt-in cutover and DI wiring.
- `BOT-098F6E` ✅: Native default rollout (`backend="auto"`) with emergency Python kill-switch.
- `BOT-098F6F` ✅: Native Equity and BOTH subplot support with dynamic indicator visibility toggling.
