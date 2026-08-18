# BOT-098F — Qt Quick Scene Graph Retained Chart Renderer Epic

**Parent:** `BOT-098`  
**Priority:** P1  
**Complexity:** L / Performance-specialized  
**Status:** Completed ✅  

## Architecture Summary

The C++ Qt Quick Scene Graph retained chart renderer replaces the CPU-heavy `QGraphicsView`/PyQtGraph for Backtest charting with a high-performance, 60 FPS GPU-retained scene graph item (`NativeChartItem`).

## Completed Sub-Phases & Slices

- **F1 (`BOT-098F1`)** ✅: CMake, MSVC, PySide6 ABI alignment, and `Sagittarius.NativeChart` QML plugin boundary.
- **F2 (`BOT-098F2`)** ✅: Retained GPU candle geometry with batched wick/body meshes.
- **F2A (`BOT-098F2A`)** ✅: Fractional camera, auto-Y scaling, and raw UTC/price axis tick contract.
- **F3 (`BOT-098F3`)** ✅: Retained volume bars and dense indicator polyline buffers.
- **F4 (`BOT-098F4`)** ✅: High-performance trade markers, crosshairs, tooltips, and dev FPS counter.
- **F5 (`BOT-098F5`)** ✅: Shared production-host A/B benchmark harness and report contract.
- **F6 (`BOT-098F6`)** ✅: Full Backtest native chart-host migration (`F6A` through `F6F`) supporting OHLC, Equity, and BOTH modes seamlessly with emergency Python fallback.
